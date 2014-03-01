#!/usr/bin/env python

"""
	DyndnsKeepAlive script (dynkas)

	Requires:
	- Python 3.x
	- a Dyndns account
	- a Gmail account with IMAP  enabled
	
"""
import getopt
import sys
import os

import smtplib
import imaplib

from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email.encoders import encode_base64

from urllib.request import urlopen

import datetime 
from datetime import date
import time

import logging
from logging import handlers 

IMAP_SERVER = 'imap.gmail.com'
IMAP_PORT = '993'
IMAP_USE_SSL = True

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = '587'

class DyndnsKeepAlive(object):
	
	def __init__(self, user, password, debug, timedelta, label):
		self.log = logging.getLogger('Dyndns auto keep-alive script')
		if(debug == True):
			self.log.setLevel(logging.DEBUG)
		else:
			self.log.setLevel(logging.WARNING)
		# add a file handler
		fh = logging.handlers.RotatingFileHandler('dynkas.log')
		if(debug == True):
			fh.setLevel(logging.DEBUG)
		else:
			fh.setLevel(logging.WARNING)
		# create a formatter and set the formatter for the handler.
		fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
		# add the Handler to the logger
		self.log.addHandler(fh)

		self.user = user
		self.password = password
		self.timedelta = timedelta
		self.label = label
				
		self.smtp = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
		
		if IMAP_USE_SSL:
			self.imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
		else:
			self.imap = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)

	def __enter__(self):
		#log in to the servers
		self.smtp.starttls()
		self.smtp.login(self.user, self.password)
		self.log.debug("SMTP login ok")
		
		self.imap.login(self.user, self.password)
		self.log.debug("IMAP login ok")
		return self

	def __exit__(self, type, value, traceback):
		# close before logout
		self.imap.close()
		self.imap.logout()	
		self.log.debug("IMAP logout ok")		
		
		self.smtp.quit()
		self.log.debug("SMTP logout ok")	

	def get_mailboxes(self):
		self.mailboxes = []
		rc, self.response = self.imap.list()
		for item in self.response:
			self.mailboxes.append(item.split()[-1])
		return rc
  
	# unused
	def get_unread_count(self):	
		# Count the unread emails, should it be unread or not? Maybe archived or not...
		status, response = self.imap.status('INBOX', "(UNSEEN)")
		unreadcount = int(response[0].split()[2].decode().strip(').,]'))
		self.log.debug('Unread emails: {n}'.format(n=unreadcount))
		return unreadcount

	# TODO use UIDs instead of volatile IDs
	def search_msgs(self, sender, subject, date):
		result, email_uids = self.imap.uid('search', None, '(SENTSINCE {date} FROM {sender} HEADER Subject "{subject}")'.format(date=date, sender=sender, subject=subject))
		#result, email_uids = self.imap.search(None, '(SENTSINCE {date} FROM {sender} HEADER Subject "{subject}")'.format(date=date, sender=sender, subject=subject))
		self.log.info('Search result: {result}. Email uids({n}): {data}'.format(result=result, n=len(email_uids), data=email_uids))
		return email_uids
		
	def fetch_message(self, uid):
		status, data = self.imap.uid('fetch', uid, '(RFC822)')
		email_msg = data[0][1]
		return email_msg
				
	# parse the whole email text for the string
	def parse_email(self, email, string, string_len):
		match = ''
		index = email.find(string)
		self.log.debug('String starts at pos: {i}'.format(i=index))
		if (index != -1):
			match = email[index:index+string_len]
		
		self.log.info('Matched string: {match}'.format(match=match))
		return match

	def archive_message(self, msg_uid, label):
		# assuming self.imap.select('Inbox')
		# move to label first
		self.log.debug("Moving message uid {u} to label{l}".format(u=msg_uid, l=label))
		res, data = self.imap.uid('STORE', msg_uid, '+X-GM-LABELS', label) 
		self.log.debug(res)
		# then archive from inbox
		self.log.debug("Archiving message uid {u} from Inbox".format(u=msg_uid)) 
		res, data = self.imap.uid('STORE', msg_uid, '+FLAGS', '\\Deleted')
		self.log.debug(res)
		
	def send_email(self, from_addr, to_addr, subject, text, file):
		self.log.debug('Sending email notification')
		email = MIMEMultipart()
		email['From'] = from_addr
		email['To'] = to_addr
		email['Date'] = formatdate(localtime=True)
		email['Subject'] = subject
		email.attach(MIMEText(text))

		if(file != None):
			part = MIMEBase('application', "octet-stream")
			fp = open(file,"rb")
			part.set_payload(fp.read())
			fp.close()
			encode_base64(part)
			part.add_header('Content-Disposition', 'attachment; filename="{f}"'.format(f=file))
			email.attach(part)
			try:
				problems = self.smtp.sendmail(from_addr, to_addr, email.as_string())
			except Exception:
				self.log.error("Unable to send email. Reasons:\n{}".format(problems))
		self.log.debug('Email sent')

	def main(self):
		self.log.info('Starting script at {now}'.format(now=datetime.datetime.now().strftime("%c")))
		# we ignore the unread, we just assume the dyndns automatic email is in the inbox
		# yet to be archived. it will be archived by the script once processed.
		self.imap.select('INBOX', False)
		
		# as the email from dyndns is automatically sent 5 and 3 days before expiration
		# setting a time delta back to 5 - 3 days seems reasonable.
		since_date = (date.today() - datetime.timedelta(self.timedelta)).strftime("%d-%b-%Y")
		self.log.info("Searching for email in inbox since: %s\n" % (since_date))
		
		sent_from = 'donotreply@dyn.com'
		with_subject = 'Your free Dyn hostname will expire'
		email_uids = self.search_msgs(sent_from, with_subject, since_date)	
		if(len(email_uids) > 0):
			link_starts_with = 'https://account.dyn.com/eml/expatconf'
			whole_link_len = 62
			
			matched_links = {}
			for uid in email_uids[0].split():
				# decode is needed to turn bytes into a string
				uid = uid.decode(encoding='UTF-8')
				email = self.fetch_message(uid)
				email = email.decode(encoding='UTF-8')
				self.log.debug('Email: {msg}\n'.format(msg=email))
				tmp = self.parse_email(email, link_starts_with, whole_link_len)
				if (tmp != ''):
					# TODO use a key value structure, with uid as key and email text as value
					# see issue #5
					matched_links[uid] = tmp
				
			self.log.info('Matched links: {l}'.format(l=matched_links.values()))
			
			# fault tolerant, just in case of more than one email in the inbox from dyn.com
			# (yet, past emails should've been archived or ignored by the time limit in the search)
			email_uids = matched_links.keys()
			if (len(email_uids) > 0):
				# only process the first link
				msg_uid, link = matched_links.popitem()
				html = urlopen(link).read().decode(encoding='UTF-8')
				# parse the html to make sure that the account will be kept alive for the next 30 days
				self.log.debug(html)	
				
				filename = ""
				attachment = None
				# error msgs about multiple KA attempts on same link
				error_msg1 = 'Error proccessing your host confirmation'
				error_msg2 = 'Your host confirmation has already been completed'		
				# confirmation of successful KA attempt
				keepalive_msg1 = 'Account Activity Confirmed'
				keepalive_msg2 = 'has been confirmed as active'

				if (error_msg1 in html and error_msg2 in html):
					text = 'The script has processed an old email from Dyndns. This shouldn\'t happen.\nTo fix this, please, manually archive all Dyndns old emails from your Inbox.'
					self.log.warning(text)
					filename = "warning.html"
				elif (keepalive_msg1 in html and keepalive_msg2 in html):
					self.log.info('Everything went fine, sending confirmation by email and archiving the email')
					# archive the dyndns request and send a notification by email that the script worked fine
					self.archive_message(msg_uid, self.label)					
					text = "The script was executed successfully on {date}.\nFor more info, check this resource: http://github.com/dynkas".format(date=datetime.datetime.now().strftime("%c"))
					filename = "confirmation.html"
				else:
					text = 'Unknown error message please report the following error as an issue here at http://github.com/dynkas\nError to report:\n\n{e}'.format(e=html)
					self.log.error(text)
					filename = "error.html"

				with open(os.path.basename(filename), "w") as attachment:
					print(html, file=attachment)
				subject = 'Dyndns auto-keep-alive script notifcation'
				self.send_email(self.user, self.user, subject, text, filename)
		else:
			self.log.info('No emails from dyn.com found as of {d}'.format(d=date.today()))
			
		self.log.info('Exiting script at {now}'.format(now=datetime.datetime.now().strftime("%c")))
		
if __name__ == '__main__':
	# default CL arg values
	username = 'name@gmail.com'
	password = 'secret'
	debug = False
	timedelta = 5
	label = 'internet/dyndns'
	
	try:
		if(len(sys.argv)<=1):
			raise(getopt.GetoptError("No arguments!"))
		else:
			opts, args = getopt.getopt(sys.argv[1:],"hu:p:dt:l:",["help","username=","password=","debug","timedelta=","label="])
	except getopt.GetoptError:
		print('Wrong or no arguments. Please, enter\n\n\tdynkas.py [-h|--help]\n\nfor usage info.')
		sys.exit(2)
		
	for opt, arg in opts:
		if opt in ("-h", "--help"):
			print('Usage: dynkas.py [OPTIONS]\n\n\
					\t-h, --help                             prints this help\n\
					\t-u, --username  <email@gmail>          your gmail address\n\
					\t-p, --password  <secret>               your secret password\n\
					\t-d, --debug                            shows debug info into log file\n\
					\t-t, --timedelta <N>                    checks emails back to N days, recommended value between 3-5\n\
					\t-l, --label     <label>                label to archive the email to, default is internet/dyndns')					
			sys.exit()
		elif opt in ("-u", "--username"):
			username = arg
		elif opt in ("-p", "--password"):
			password = arg
		elif opt in ("-d", "--debug"):
			debug = True
		elif opt in ("-t", "--timedelta"):
			try:
				timedelta = int(arg)
			except exceptions.ValueError:
				timedelta = 5
				w = "Error parsing {td} into integer. Using default timedelta of {dtd}".format(td=arg, dtd=timedelta)
				print(w)
				self.log.warning(w)
		elif opt in ("-l", "--label"):
			label = arg

	with DyndnsKeepAlive(username, password, debug, timedelta, label) as kas:
		kas.main()
