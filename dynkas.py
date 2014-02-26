#!/usr/bin/env python

"""DyndnsKeepAlive.

	Requires Python 3.x
	IMAP and Dyndns accounts
	
"""

import smtplib
import imaplib

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
	
	def __init__(self, user, password):
		self.log = logging.getLogger('Dyndns auto keep-alive script')
		self.log.setLevel(logging.DEBUG)
		# add a file handler
		fh = logging.handlers.RotatingFileHandler('dynkas.log')
		fh.setLevel(logging.DEBUG)
		# create a formatter and set the formatter for the handler.
		fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
		# add the Handler to the logger
		self.log.addHandler(fh)

		self.user = user
		self.password = password
				
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
  
	def get_unread_count(self):	
		# Count the unread emails, should it be unread or not? Maybe archived or not...
		status, response = self.imap.status('INBOX', "(UNSEEN)")
		unreadcount = int(response[0].split()[2].decode().strip(').,]'))
		self.log.debug('Unread emails: {n}'.format(n=unreadcount))
		return unreadcount

	def search_msgs(self, sender, subject, date):
		# TODO turn on/off data check by CL switch
		# result, email_ids = self.imap.search(None, '(FROM {sender} HEADER Subject "{subject}")'.format(date=date, sender=sender, subject=subject))
		result, email_ids = self.imap.search(None, '(SENTSINCE {date} FROM {sender} HEADER Subject "{subject}")'.format(date=date, sender=sender, subject=subject))
		self.log.info('Search result: {result}. Email ids({n}): {data}'.format(result=result, n=len(email_ids), data=email_ids))
		return email_ids
		
	def fetch_message(self, num):
		status, data = self.imap.fetch(num, '(RFC822)')
		#email_msg = email.message_from_string(data[0][1])
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

	def archive_message(self, msg_uid):
		# assuming self.imap.select('Inbox')
		# make sure it is marked as read
		print (msg_uid)
		# archive
		typ, data = self.imap.uid('STORE', msg_uid, '+X-GM-LABELS', 'internet/dyndns')
		# move from inbox
		typ, data = self.imap.uid('STORE', msg_uid, '-X-GM-LABELS', '\Inbox')
		
	def send_email(self, from_addr, to_addr, subject, text):
		header  = 'From: %s\n' % from_addr
		header += 'To: %s\n' % ','.join(to_addr)
		header += 'Subject: %s\n\n' % subject
		email = header + text
		problems = self.smtp.sendmail(from_addr, to_addr, email)

	# def print_msg(self, num):
		# self.imap.select('Inbox')
		# status, data = self.imap.fetch(num, '(RFC822)')
		# print 'Message %s\n%s\n' % (num, data[0][1])

	def main(self):
		self.log.info('Starting script at {now}'.format(now=datetime.datetime.now().strftime("%c")))
		self.imap.select('INBOX')
		# unread = self.get_unread_count()
		# we ignore the unread, we just assume the dyndns automatic email is in the inbox
		# yet to be archived. it will be archived by the script once processed.
		
		# check for new mail from dyndns since last check (yesteday)
		# TODO need to store last datetime instead of timedelta[1] (1 day) 
		# as the email from dyndns is automatically sent 5 and 3 days before expiration
		# setting a time delta back to 5 or 3 +1 days seems reasonable.
		since_date = (date.today() - datetime.timedelta(5)).strftime("%d-%b-%Y")
		self.log.info("Searching for email in inbox since: %s\n" % (since_date))
		
		sent_from = 'donotreply@dyn.com'
		with_subject = 'Your free Dyn hostname will expire'
		email_ids = self.search_msgs(sent_from, with_subject, since_date)	
		if(len(email_ids) > 0):
			link_starts_with = 'https://account.dyn.com/eml/expatconf'
			whole_link_len = 62
			
			matched_links = {}
			for id in email_ids[0].split():
				email = self.fetch_message(id)
				email = email.decode(encoding='UTF-8')
				#self.log.debug('Email: {msg}\n'.format(msg=email))
				tmp = self.parse_email(email, link_starts_with, whole_link_len)
				if (tmp != ''):
					# TODO use a key value structure, with id as key and email text as value
					matched_links[id] = tmp
				
			self.log.info('Matched links: {l}'.format(l=matched_links.values()))
			
			# fault tolerant, just in case of more than one email in the inbox from dyn.com
			# (yet, past emails should've been archived or ignored by the time limit in the search)
			email_ids = matched_links.keys()
			if (len(email_ids) > 0):
				# only process the first link
				msg_id, link = matched_links.popitem()
				html = urlopen(link).read().decode(encoding='UTF-8')
				# parse the html to make sure that the account will be kept alive for the next 30 days
				# self.log.debug(html)	
				# error msgs about multiple KA attempts on same link
				error_msg1 = 'Error proccessing your host confirmation'
				error_msg2 = 'Your host confirmation has already been completed'		
				# confirmation of successful KA attempt
				keepalive_msg1 = 'Account Activity Confirmed'
				keepalive_msg2 = 'has been confirmed as active'				
				if (error_msg1 in html and error_msg2 in html):
					self.log.warning('The script has processed an old email from Dyndns. This shouldn\'t happen. To fix this, please, manually archive all Dyndns old emails from your Inbox.')
				elif (keepalive_msg1 in html and keepalive_msg2 in html):
					self.log.info('Everything went fine, sending confirmation by email and archiving the email')
					# archive the dyndns request and send a notification by email that the script worked fine
					self.archive_message(msg_id)
					subject = 'Dyndns auto-keep-alive script notifcation'
					text = "The script was executed successfully on {date}.\n For more info, check this resource: http://github.com/dyndns-kas".format(date=datetime.datetime.now().strftime("%c"))
					self.send_email(imap_username, imap_username, subject, text);
				else:
					self.log.error('Unknown error message please report the following error as an issue here at http://github.com/dyndns-kas\nError to report:\n\n{e}'.format(e=html))
		else:
			self.log.info('No emails from dyn.com found as of {d}'.format(d=date.today()))
			
		self.log.info('Exiting script at {now}'.format(now=datetime.datetime.now().strftime("%c")))
	
if __name__ == '__main__':
	# example:
	imap_username = 'dummy@gmail.com'
	imap_password = '#secret'
	with DyndnsKeepAlive(imap_username, imap_password) as kas:
		kas.main()