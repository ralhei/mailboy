"""Main mailboy module."""
import sys
import ssl
import time
import email
import smtplib
import logging

from imapclient import IMAPClient

from . import config

MAX_IMAP_IDLE_SECS = 300

logger = logging.getLogger('mailboy')


def cleanup_subject(msg):
    orig_subject = msg['Subject']
    del msg['Subject']
    # For replies remove previous occurence of HB2.0 from subject:
    msg['Subject'] = config.SUBJECT_PREFIX + ' ' + orig_subject.replace(config.SUBJECT_PREFIX, '')


def distribute_message(smtp, msg, recipients):
    for recipient in recipients:
        del msg['To']
        msg['To'] = recipient
        try:
            smtp.send_message(msg)
        except smtplib.SMTPException:
            logger.error('Failed to send message to %s', recipient)
        else:
            logger.debug('Sent mail to %s', recipient)


def publish_accepted_messages(imap):
    logger.debug('Starting to search for and publish accepted messages.')
    message_uids = imap.search()
    logger.debug('Found %d accepted messages.', len(message_uids))
    if not message_uids:
        return

    context = ssl.create_default_context()
    logger.debug('Connecting to SMTP account at %s', config.SMTP_HOST)
    with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context) as smtp:
        logger.debug('Login to SMTP with user %s', config.SMTP_USER)
        smtp.login(config.SMTP_USER, config.SMTP_SECRET)

        for uid, message_data in imap.fetch(message_uids, 'RFC822').items():
            msg = email.message_from_bytes(message_data[b'RFC822'])
            logger.debug('MSG: from: %s, subject: %s', msg['From'], msg['Subject'])
            cleanup_subject(msg)
            distribute_message(smtp, msg, config.RECIPIENTS)
            target_folder = config.PUBLISHED_FOLDER
            logger.debug('Moving message into "%s" folder.', target_folder)
            imap.move(uid, target_folder)


def init_imap_folder_structure(imap):
    for folder in config.ALL_FOLDERS:
        logger.debug('Checking if folder "%s" exists.', folder)
        if not imap.folder_exists(folder):
            logger.info('Creating IMAP folder "%s"', folder)
            imap.create_folder(folder)
            imap.subscribe_folder(folder)


def imap_poll_loop(imap, max_count=1, interval=10):
    counter = 0
    while True:
        publish_accepted_messages(imap)
        counter += 1
        if max_count is None or counter < max_count:
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                break
        else:
            break


def imap_idle_loop(imap):
    # Send existing message first before going into IDLE mode:
    publish_accepted_messages(imap)
    # Start IDLE mode
    imap.idle()
    logger.debug('Starting imap idle loop.')
    while True:
        try:
            responses = imap.idle_check(timeout=MAX_IMAP_IDLE_SECS)
            # Turn idle mode on and of after each timeout to refresh TCP connection.
            # Idle must also be turned off before calling publish_accepted_messages()
            imap.idle_done()
            if responses:
                publish_accepted_messages(imap)
            else:
                logger.debug('Idle cycle found no new messages.')
            imap.idle()
        except KeyboardInterrupt:
            imap.idle_done()
            break


def run(mode, poll_interval):
    logger.debug('Connecting to IMAP account at %s', config.IMAP_HOST)
    with IMAPClient(config.IMAP_HOST) as imap:
        logger.debug('Login to IMAP with user %s', config.IMAP_USER)
        imap.login(config.IMAP_USER, config.IMAP_SECRET)
        init_imap_folder_structure(imap)
        imap.select_folder(config.ACCEPTED_FOLDER)

        if mode == 'idle':
            imap_idle_loop(imap)
        else:
            max_count = 1 if mode == 'single' else None
            imap_poll_loop(imap, max_count, poll_interval)
