"""Main mailboy module."""
import ssl
import time
import email
import smtplib
import logging

from imapclient import IMAPClient

MAX_IMAP_IDLE_SECS = 300

logger = logging.getLogger('mailboy')


def cleanup_subject(config, msg):
    orig_subject = msg['Subject']
    del msg['Subject']
    # For replies remove previous occurence of HB2.0 from subject:
    msg['Subject'] = \
        config.mailinglist.SUBJECT_PREFIX + ' ' + \
        orig_subject.replace(config.mailinglist.SUBJECT_PREFIX, '')


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


def load_recipients(config):
    recipients = open(config.mailinglist.RECIPIENTS).readlines()
    # Strip spaces and tabs around email addresses:
    recipients = [r.strip() for r in recipients]
    # Remove empty lines and lines beginning with a hash (i.e. comments):
    recipients = [r for r in recipients if r and not r.startswith('#')]
    return recipients


def publish_accepted_messages(config, imap):
    logger.debug('Starting to search for and publish accepted messages.')
    message_uids = imap.search()
    logger.debug('Found %d accepted messages.', len(message_uids))
    if not message_uids:
        return

    recipients = load_recipients(config)

    context = ssl.create_default_context()
    logger.debug('Connecting to SMTP account at %s', config.smtp.SMTP_HOST)
    with smtplib.SMTP_SSL(config.smtp.SMTP_HOST, config.smtp.SMTP_PORT, context=context) as smtp:
        logger.debug('Login to SMTP with user %s', config.smtp.SMTP_USER)
        smtp.login(config.smtp.SMTP_USER, config.smtp.SMTP_PWD)

        for uid, message_data in imap.fetch(message_uids, 'RFC822').items():
            msg = email.message_from_bytes(message_data[b'RFC822'])
            msg['Reply-To'] = config.smtp.MAIL_USER
            logger.debug('MSG: from: %s, subject: %s', msg['From'], msg['Subject'])
            cleanup_subject(config, msg)
            distribute_message(smtp, msg, recipients)
            target_folder = config.folders.PUBLISHED_FOLDER
            logger.debug('Moving message into "%s" folder.', target_folder)
            imap.move(uid, target_folder)


def init_imap_folder_structure(config, imap):
    for folder in [config.folders.ACCEPTED_FOLDER, config.folders.PUBLISHED_FOLDER]:
        logger.debug('Checking if folder "%s" exists.', folder)
        if not imap.folder_exists(folder):
            logger.info('Creating IMAP folder "%s"', folder)
            imap.create_folder(folder)
            imap.subscribe_folder(folder)


def imap_poll_loop(config, imap, max_count=1, interval=10):
    counter = 0
    while True:
        publish_accepted_messages(config, imap)
        counter += 1
        if max_count is None or counter < max_count:
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                break
        else:
            break


def imap_idle_loop(config, imap):
    # Send existing message first before going into IDLE mode:
    publish_accepted_messages(config, imap)
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
                publish_accepted_messages(config, imap)
            else:
                logger.debug('Idle cycle found no new messages.')
            imap.idle()
        except KeyboardInterrupt:
            imap.idle_done()
            break


def run(config, mode, poll_interval):
    logger.debug('Connecting to IMAP account at %s', config.imap.IMAP_HOST)
    with IMAPClient(config.imap.IMAP_HOST) as imap:
        logger.debug('Login to IMAP with user %s', config.imap.IMAP_USER)
        imap.login(config.imap.IMAP_USER, config.imap.IMAP_PWD)
        init_imap_folder_structure(config, imap)
        imap.select_folder(config.folders.ACCEPTED_FOLDER)

        if mode == 'idle':
            imap_idle_loop(config, imap)
        else:
            max_count = 1 if mode == 'single' else None
            imap_poll_loop(config, imap, max_count, poll_interval)
