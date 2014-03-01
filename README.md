dynkas
======
Dyndns keep-alive script is a Python scripts that prevents free Dyndns accounts to expire. In fac, in case of non-premium accouts, Dyndns.com sends automatic messages 
every 30 days. Such emails contain a link a link that must be open to prevent the account to expire. 
This script automatically checks your inbox for such email messages sent from Dyndns.com, opens the link and archive those emails.

Requirements
------------
* Dyndns free account
* GMail account with IMAP access enabled
* Pyhton 3+

Usage instructions
------------------
Launch from cron or command line.

Usage: 
`dynkas.py [OPTIONS]`
* `-h, --help`                             prints this help
* `-u, --username email@gmail`          your gmail address
* `-p, --password secret`               your secret password
* `-d, --debug`                            shows debug info into log file
* `-t, --timedelta N`                    checks emails back to N days, 5 default`

Known issues & limitations
--------------------------
As of now, archiving processed messages does not work. See issue #3.
