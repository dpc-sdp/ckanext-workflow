import ckan.lib.jinja_extensions as jinja_extensions
import ckan.lib.mailer as mailer
import ckan.plugins.toolkit as toolkit
import logging
import os

from ckanapi import RemoteCKAN, NotFound

log = logging.getLogger(__name__)

# ODP_API_KEY and ODP_URL should be set as a Lagoon environment variables
odp_api_key = os.getenv('ODP_API_KEY')
odp_url = os.getenv('ODP_URL')


def purge_dataset_from_odp(context, pkg_dict):
    '''
    Helper function to purge a dataset from the Data.Vic ODP (public) CKAN instance
    when it is deleted from the IAR (private) CKAN instance.

    CONTEXT: this was previously handled as a cron job on the ODP
    (ref.: scripts/ckan/ckan-harvest-deleter.sh)

    The cron job called a command in the `ckanext-harvest-deleter` extension
    which checked the `recently_changed_package_activity_list` from the IAR
    then deleted any datasets with a `deleted package` activity.

    That approach no longer works reliably, so a deletion from the source (IAR)
    now triggers a deletion from the destination (ODP).

    :param pkg_dict: Passed in from the `after_delete` interface method (only contains `id`)
    :return:
    '''
    pkg_id = pkg_dict.get('id', None) or None

    # If either ODP_API_KEY or ODP_URL envvars not set - do not proceed further
    if not odp_api_key or not odp_url:
        # Notify data.vic@salsadigital.com.au email group via Job Worker
        toolkit.enqueue_job(send_deletion_notification_email, [
            'odp_envvars_not_set',
            {
                'environment': os.getenv('LAGOON_GIT_SAFE_BRANCH', 'Local'),
                'odp_api_key': os.getenv('ODP_API_KEY', 'Not set'),
                'odp_url': os.getenv('ODP_URL', 'Not set'),
            }
        ])
        return False

    if pkg_id:
        odp_pkg = get_odp_package(context, pkg_id)

        if odp_pkg:
            log.debug('>>> Queueing job to send ODP purge request for pkg ID: {0} - name: {1}'.format(odp_pkg.get('id'), odp_pkg.get('name')))
            toolkit.enqueue_job(send_package_purge_request, [
                odp_pkg
            ])


def get_odp_package(context, pkg_id):
    odp_pkg = None

    odp = RemoteCKAN(odp_url, odp_api_key)

    try:
        # 1. Try to locate the package on ODP using the IAR package ID
        odp_pkg = odp.action.package_show(id=pkg_id)
    except NotFound as e:
        # 2. If that fails try locating the package by name from the ODP
        log.error('Failed to locate IAR package ID: {0} by ID on ODP - Exception: {1}'.format(pkg_id, str(e)))

        try:
            # The `after_delete` interface method only provides deleted package ID
            # so we need to call `package_show` locally to get the package name
            pkg_dict = toolkit.get_action('package_show')(context, {'id': pkg_id})
            pkg_name = pkg_dict.get('name')

            # Attempt to fetch package from ODP by name
            odp_pkg = odp.action.package_show(id=pkg_name)
        except Exception as e:
            log.error(
                'Failed to locate IAR package by ID: {0} or Name: \'{1}\' on ODP - Exception: {2}'.format(pkg_id,
                                                                                                          pkg_name,
                                                                                                          str(e)))
    except Exception as e:
        log.error('Failed to locate IAR package by ID: {0} on ODP - Exception: {1}'.format(pkg_id, str(e)))

    return odp_pkg


def package_has_harvest_url(odp_pkg_extras):
    '''
    Check the ODP package's extras for any extra with a value of 'harvest_url',
    indicating the ODP dataset was created via a harvest from the IAR
    :param pkg_extras:
    :return:
    '''
    if isinstance(odp_pkg_extras, list):
        for extra in odp_pkg_extras:
            harvest_url = any(value for key, value in extra.items() if key == 'key' and value == 'harvest_url')
            if harvest_url:
                return True
    return False


def send_package_purge_request(odp_pkg):
    '''
    Send a `dataset_purge` request to the ODP API
    :param odp_pkg:
    :return:
    '''
    email_template = 'odp_deletion_success'
    email_vars = {
        'environment': os.getenv('LAGOON_GIT_SAFE_BRANCH', 'Local'),
        'exception': None,
        'id': odp_pkg.get('id'),
        'name': odp_pkg.get('name'),
        'odp_url': odp_url,
        'pkg_dict': odp_pkg,
    }

    log.debug('>>> Sending ODP package purge request for pkg ID: {0} - name: {1} <<<'.format(odp_pkg.get('id'), odp_pkg.get('name')))
    odp = RemoteCKAN(odp_url, odp_api_key)

    try:
        odp.action.dataset_purge(id=odp_pkg.get('id'))
    except Exception as e:
        email_template = 'odp_deletion_failure'
        email_vars['exception'] = str(e)

    send_deletion_notification_email(
        email_template,
        email_vars,
    )


def send_deletion_notification_email(template, data_dict, email_addresses=None):
    '''
    Ideally this should be called via:

        toolkit.enqueue_job(send_deletion_notification_email, [ ... ])

    :param template:
    :param data_dict:
    :param email_addresses:
    :return:
    '''
    # For future expansion, i.e. to add more recipients for notifications
    if not email_addresses:
        email_addresses = [toolkit.config.get('email_to')]

    subject = render_jinja2('emails/subjects/{0}.txt'.format(template), data_dict)
    body = render_jinja2('emails/bodies/{0}.txt'.format(template), data_dict)

    for email in email_addresses:
        try:
            if email:
                log.debug('Attempting to send {0} to: {1}'.format(template, email))
                mail_dict = {
                    'recipient_name': email,
                    'recipient_email': email,
                    'subject': subject,
                    'body': body
                }
                mailer.mail_recipient(**mail_dict)
        except mailer.MailerException as e:
            log.error(u'Failed to send email {0} to {1}.'.format(template, email))
            log.error('Error: {}'.format(e))


def render_jinja2(template_name, extra_vars):
    # CKAN Job worker does to use pylons/flask request so we can not use toolkit.render
    # Need to setup/create our own jinja env to get and render templates
    env = jinja_extensions.Environment(**jinja_extensions.get_jinja_env_options())
    template = env.get_template(template_name)
    return template.render(**extra_vars)
