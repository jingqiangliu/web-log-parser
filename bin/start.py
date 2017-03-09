# -*- coding:utf-8 -*-
import time
import datetime
import os
import re
from collections import Counter
from numpy import var, average, percentile

from util import get_dir_files
from config import config
from report import generate_web_log_parser_report
from report import generate_web_log_parser_urls
from report import update_index_html


class URLData:

    def __init__(self, url=None, pv=None, ratio=None, peak=None):
        self.url = url
        self.pv = pv
        self.ratio = ratio
        self.peak = peak
        self.time = []
        self.cost = []
        self.cost_time = {'p9': None, 'p8': None, 'p5': None, 'avg': None, 'variance': None}

def parse_log_format():
    log_format_index = {}
    log_format_list = config.log_format.split()
    for item in log_format_list:
        if item == 'ip':
            log_format_index.setdefault('ip_index', log_format_list.index(item)+1)
        if item == 'real_ip':
            log_format_index.setdefault('real_ip_index', log_format_list.index(item)+1)
        if item == 'datetime':
            log_format_index.setdefault('time_index', log_format_list.index(item)+1)
        if item == 'url':
            log_format_index.setdefault('url_index', log_format_list.index(item)+1)
        if item == 'method':
            log_format_index.setdefault('method_index', log_format_list.index(item)+1)
        if item == 'protocol':
            log_format_index.setdefault('protocol_index', log_format_list.index(item)+1)
        if item == 'cost':
            log_format_index.setdefault('cost_time_index', log_format_list.index(item)+1)
    if 'real_ip_index' in log_format_index.keys():
        log_format_index.setdefault('host_index', log_format_list.index('real_ip')+1)
    else:
        log_format_index.setdefault('host_index', log_format_list.index('ip')+1)
    return log_format_index


def not_static_file(url):
    url_front = url.split('?')[0]
    if url_front.split('.')[-1] not in config.static_file:
        return True
    else:
        return False


def is_ignore_url(url):
    url_front = url.split('?')[0]
    if url_front not in config.ignore_urls:
        return False
    else:
        return True


def get_new_url(origin_url):
    if len(origin_url.split('?')) == 1:
        return origin_url
    url_front = origin_url.split('?')[0]
    url_parameters = sorted(origin_url.split('?')[1].split('&'))
    new_url_parameters = []
    for parameter in url_parameters:
        key = parameter.split('=')[0]
        if len(parameter.split('=')) == 1:
            new_url_parameters.append(parameter)
        elif key in config.custom_keys:
            new_url_parameters.append(key + '=' + config.custom_parameters.get(key))
        elif key in config.fixed_parameter_keys:
            new_url_parameters.append(parameter)
        else:
            new_url_parameters.append(key + '=' + '{' + key + '}')
    new_url = url_front + '?' + '&amp;'.join(new_url_parameters)
    return new_url


def parse_log_file(target_file, log_format):
    hosts = []
    times = []
    hours = []
    minutes = []
    urls = []
    pattern = re.compile(config.log_pattern)
    with open('../data/'+target_file, 'r') as f:
        for line in f:
            match = pattern.match(line)
            if match is None:
                continue
            if config.is_with_parameters:
                url = get_new_url(match.group(log_format.get('url_index')))
            else:
                url = match.group(log_format.get('url_index')).split('?')[0]
            if is_ignore_url(url):
                continue
            hosts.append(match.group(log_format.get('host_index')).split(',')[0])
            log_time = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(match.group(log_format.get('time_index')),
                                                                        '%d/%b/%Y:%H:%M:%S'))
            times.append(log_time)
            hours.append(log_time.split(':')[0])
            minutes.append(':'.join(log_time.split(':')[0:-1]))
            if not_static_file(url):
                method = match.group(log_format.get('method_index'))
                protocol = match.group(log_format.get('protocol_index'))
                urls.append(method+' '+url+' '+protocol)

    pv = len(times)
    uv = len(set(hosts))
    response_avg = int(pv/len(set(times)))

    hours_counter = Counter(hours)
    minutes_counter = Counter(minutes)
    times_counter = Counter(times)

    response_most_common = times_counter.most_common(1)[0]
    response_peak = response_most_common[1]
    response_peak_time = response_most_common[0]

    urls_counter = Counter(urls)
    urls_most_common = urls_counter.most_common(config.urls_most_number)

    url_data_list = []
    for item in urls_most_common:
        ratio = '%0.3f' % float(item[1]*100/float(pv))
        url_data_list.append(URLData(url=item[0], pv=item[1], ratio=ratio))

    with open('../data/'+target_file, 'r') as f:
        for line in f:
            match = pattern.match(line)
            method = match.group(log_format.get('method_index'))
            if config.is_with_parameters:
                url = get_new_url(match.group(log_format.get('url_index')))
            else:
                url = match.group(log_format.get('url_index')).split('?')[0]
            protocol = match.group(log_format.get('protocol_index'))
            for url_data in url_data_list:
                if url_data.url == method+' '+url+' '+protocol:
                    url_data.time.append(match.group(log_format.get('time_index')))
                    if 'cost_time_index' in log_format.keys():
                        url_data.cost.append(float(match.group(log_format.get('cost_time_index'))))
                    break

    for url_data in url_data_list:
        url_data.peak = Counter(url_data.time).most_common(1)[0][1]
        if url_data.cost:
            url_data.cost_time['avg'] = '%0.3f' % float(average(url_data.cost))
            url_data.cost_time['variance'] = int(var(url_data.cost))
            url_data.cost_time['p9'] = '%0.3f' % percentile(url_data.cost, 90)
            url_data.cost_time['p8'] = '%0.3f' % percentile(url_data.cost, 80)
            url_data.cost_time['p5'] = '%0.3f' % percentile(url_data.cost, 50)

    total_data = {'pv': pv, 'uv': uv, 'response_avg': response_avg, 'response_peak': response_peak,
                  'response_peak_time': response_peak_time, 'url_data_list': url_data_list,
                  'source_file': target_file, 'hours_hits': hours_counter, 'minutes_hits': minutes_counter,
                  'second_hits': times_counter}
    generate_web_log_parser_report(total_data)

    total_data = {'source_file': target_file, 'urls': urls_counter}
    generate_web_log_parser_urls(total_data)


def parse_log_file_with_goaccess(target_file):
    source_file = '../data/' + target_file
    goaccess_file = '../result/report/' + target_file + '_GoAccess.html'
    command = """ goaccess -f %(file)s  -a -q \
            --time-format=%(time_format)s \
            --date-format=%(date_format)s \
            --log-format='%(goaccess_log_format)s' \
            --no-progress > %(goaccess_file)s""" \
              % {'file': source_file, 'time_format': config.time_format, 'date_format': config.date_format,
                 'goaccess_log_format': config.goaccess_log_format, 'goaccess_file': goaccess_file}
    os.system(command)


def main():

    log_format = parse_log_format()

    result_files = [result_file.replace('.html', '') for result_file in get_dir_files('../result/report/')]
    target_files = sorted([data_file for data_file in get_dir_files('../data') if data_file not in result_files])

    for target_file in target_files:
        print datetime.datetime.now(), ' Start parse file : '+target_file

        parse_log_file(target_file, log_format)
        if config.goaccess_flag:
            parse_log_file_with_goaccess(target_file)

        print datetime.datetime.now(), ' End parse file: '+target_file

    update_index_html()

if __name__ == '__main__':
    main()
