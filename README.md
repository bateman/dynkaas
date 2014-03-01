dynkas
======
**_Dyndns keep-alive script_** is a Python scripts that prevents free Dyndns accounts to expire. In fact, in case of non-premium accouts, Dyndns.com sends to their users automatic email messages every 30 days. Such emails contain a link that must be opened to prevent the account to expire. 

This script automatically checks your inbox for such email messages sent from Dyndns.com, parses them, opens the link and archive those emails.
Confirmation messages are sent by the script in case of success or failure, so that users what to do.

Requirements
------------
* Dyndns free account
* GMail account with IMAP access enabled
* Pyhton 3+
* Emails must be in Inbox (i.e., not archived). May also have other labels.

Usage instructions
------------------
Launch from cron or command line. **Safest bet is to run it every day, at most evey 3**. Although Dyndns sends these messages every 30 days, you cannot run the script every 30 days too. If you run the script on the 30th day _before_  acutally getting the email, that would expire before next execution, and so would your free account.

Usage: 
`dynkas.py [OPTIONS]`
* `-h, --help` &nbsp;&nbsp;&nbsp;&nbsp; prints this help
* `-u, --username email@gmail` &nbsp;&nbsp;&nbsp;&nbsp; your gmail address
* `-p, --password secret` &nbsp;&nbsp;&nbsp;&nbsp; your secret password
* `-d, --debug` &nbsp;&nbsp;&nbsp;&nbsp; shows debug info into log file
* `-t, --timedelta N` &nbsp;&nbsp;&nbsp;&nbsp;  checks emails back to N days, 5 default

Known issues & limitations
--------------------------
As of now, archiving processed messages in GMail does not work yet. See issue #3 description for more.
