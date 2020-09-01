# -*- coding=utf-8 -*-

import json
import sys
import getopt
import urllib.request
import logging
from logging.handlers import TimedRotatingFileHandler

from aliyunsdkcore.client import AcsClient
from aliyunsdkalidns.request.v20150109.AddDomainRecordRequest import AddDomainRecordRequest
from aliyunsdkalidns.request.v20150109.DescribeDomainRecordsRequest import DescribeDomainRecordsRequest
from aliyunsdkalidns.request.v20150109.UpdateDomainRecordRequest import UpdateDomainRecordRequest
from aliyunsdkcore.acs_exception.exceptions import ClientException
from aliyunsdkcore.acs_exception.exceptions import ServerException

import smtplib
from email.mime.text import MIMEText
from email.header import Header

# ------------------------------------define function--------------------------------------


def get_log(name="main"):
    log_file_name = "./aliyunDns.log"
    log_fmt = '%(asctime)s\tFile \"%(filename)s\",line %(lineno)s\t%(levelname)s: %(message)s'
    formatter = logging.Formatter(log_fmt)

    log_file_handler = TimedRotatingFileHandler(filename=log_file_name, when="D", interval=7, backupCount=2)
    log_file_handler.setFormatter(formatter)
    logging.basicConfig(level=logging.DEBUG)
    inner_log = logging.getLogger(name)
    inner_log.addHandler(log_file_handler)
    return inner_log


log = get_log()


class DnsRecord(object):
    def __init__(self):
        self.domain_name = ''
        self.record_id = ''
        self.rr = ''
        self.dr_type = ''
        self.value = ''


def log_begin():
    log.info("----------------------------------------begin-------------------------------------")


def log_and_exit(err):
    log.info("----------------------------------------end---------------------------------------\r\n\r\n")
    sys.exit(err)


def get_wlan_ip():
    connect = urllib.request.urlopen("http://members.3322.org/dyndns/getip")
    status = connect.status
    reason = connect.reason
    if status != 200:
        log.error("get ip request status " + status + " reason " + reason)
        return ''
    read = connect.readline()
    connect.close()
    ip = read.decode("utf-8")
    ip = ip.rstrip("\n").lstrip('b')
    log.debug("ip " + ip)
    return ip


def add_dns_record(ali_api_id, ali_api_secret, ip, request_domain, request_sub_domain):
    client = AcsClient(ali_api_id, ali_api_secret, 'cn-hangzhou')

    request = AddDomainRecordRequest()
    request.set_accept_format('json')

    request.set_DomainName(request_domain)
    request.set_RR(request_sub_domain)
    request.set_Type("A")
    request.set_Value(ip)
    try:
        response = client.do_action_with_exception(request)
    except (ClientException, ServerException) as reason:
        log.error("add dns failed. do_action_with_exception " + reason)
        return False

    result = str(response, encoding='utf-8')
    log.info("add dns record result: \r\n" + result)
    json_obj = json.loads(result)

    if len(json_obj['RecordId']) == 0:
        log.error("add dns failed. error code " + json_obj['code'])
        return False
    return True


def get_dns_record(ali_api_id, ali_api_secret, request_domain, request_sub_domain):
    client = AcsClient(ali_api_id, ali_api_secret, 'cn-hangzhou')

    request = DescribeDomainRecordsRequest()
    request.set_accept_format('json')

    request.set_DomainName(request_domain)
    request.set_PageSize("500")
    request.set_RRKeyWord(request_sub_domain)
    request.set_TypeKeyWord("A")

    try:
        response = client.do_action_with_exception(request)
    except (ClientException, ServerException) as reason:
        log.error("get dns failed. do_action_with_exception " + reason)
        return DnsRecord()

    result = str(response, encoding='utf-8')
    log.info("get dns record result: \r\n" + result)
    json_obj = json.loads(result)
    domain_records = json_obj['DomainRecords']
    records = domain_records['Record']
    ali_dns_record = DnsRecord()
    for record in records:
        if record['RR'] == request_sub_domain and record['DomainName'] == request_domain:
            ali_dns_record.domain_name = record['DomainName']
            ali_dns_record.record_id = record['RecordId']
            ali_dns_record.rr = record['RR']
            ali_dns_record.dr_type = record['Type']
            ali_dns_record.value = record['Value']

        else:
            continue
    return ali_dns_record


def update_dns_record(ali_api_id, ali_api_secret, ip, record_id, request_sub_domain):
    client = AcsClient(ali_api_id, ali_api_secret, 'cn-hangzhou')

    request = UpdateDomainRecordRequest()
    request.set_accept_format('json')

    request.set_RecordId(record_id)
    request.set_RR(request_sub_domain)
    request.set_Type("A")
    request.set_Value(ip)

    try:
        response = client.do_action_with_exception(request)
    except (ClientException, ServerException) as reason:
        log.error("update dns failed. do_action_with_exception")
        return False

    result = str(response, encoding='utf-8')
    log.info("update dns record result: \r\n" + result)
    json_obj = json.loads(result)

    if len(json_obj['RecordId']) == 0:
        log.error("update dns failed. error code " + json_obj['code'])
        return False
    return True


def send_email(message, sender_server, sender_port, sender_user, sender_pwd, sender_addr, receiver_addr):
    message = MIMEText(message, 'plain', 'utf-8')
    message['From'] = Header("alidns shell", 'utf-8')
    message['To'] = Header("receiver", 'utf-8')

    subject = message
    message['Subject'] = Header(subject, 'utf-8')

    try:
        smtp_obj = smtplib.SMTP()
        smtp_obj.connect(sender_server, sender_port)
        smtp_obj.login(sender_user, sender_pwd)
        smtp_obj.sendmail(sender_addr, receiver_addr, message.as_string())
        log.info("email send suc!")
    except smtplib.SMTPException:
        log.error("email send failed!")


# ----------------------------------run begin--------------------------------

api_id = ''
api_key = ''
domain = ''
sub_domain = ''

log_begin()

try:
    opts, args = getopt.getopt(sys.argv[1:], "hi:k:d:s:", ["apiId=", "apiKey=", "domain=", "subDomain="])
except getopt.GetoptError:
    log.critical("args error: " + sys.argv)
    log_and_exit(1)
for opt, arg in opts:
    if arg == '-h':
        print('example.py -i <apiId> or --apiId=<apiId> /r/n'
              '-k <apiKey> or --apiKey=<apiKey> /r/n'
              '-d <domain> or --domain=<domain> /r/n'
              '-s <subDomain> or --subDomain=<subDomain> ')
    elif opt in ('-i', "apiId"):
        api_id = arg
    elif opt in ('-k', "apiKey"):
        api_key = arg
    elif opt in ('-d', "domain"):
        domain = arg
    elif opt in ('-s', "subDomain"):
        sub_domain = arg

log.debug("apiId = %s , apiKey = %s, domain = %s, subDomain= %s", api_id != '', api_key != '', domain, sub_domain)

if len(api_id) == 0 or len(api_key) == 0 or len(domain) == 0 or len(sub_domain) == 0:
    log.critical("args error: " + "".join(sys.argv))
    log_and_exit(1)

dns_record = get_dns_record(api_id, api_key, domain, sub_domain)
new_ip = get_wlan_ip()

log.info("dns_record: " + str(dns_record.__dict__))

if new_ip == dns_record.value:
    log.info("ip is same, don't need update record")
    log_and_exit(0)

# ip not exist, add record
if len(dns_record.domain_name) == 0:
    log.info("ip not exist, add record")
    add_dns_record(api_id, api_key, new_ip, domain, sub_domain)
# ip exist, update record
elif new_ip != dns_record.value and new_ip not in dns_record.value:
    log.info("ip exist, update record")
    update_dns_record(api_id, api_key, new_ip, dns_record.record_id, sub_domain)

log_and_exit(0)

