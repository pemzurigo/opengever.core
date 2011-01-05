from Acquisition import aq_parent
from Products.CMFCore.interfaces._tools import IMemberData
from Products.PluggableAuthService.interfaces.authservice import IPropertiedUser
from opengever.ogds.base.interfaces import IContactInformation
from opengever.tabbedview import _
from plone.memoize import ram
from zope.component import getUtility


def task_id_checkbox_helper(item, value):
    """ Checkbox helper based on tasks id attribute
    """

    attrs = {
        'type': 'checkbox',
        'class': 'noborder selectable',
        'name': 'task_ids:list',
        'id': item.task_id,
        'value': item.task_id,
        'title': 'Select %s' % item.title,
        }

    return '<input %s />' % ' '.join(['%s="%s"' % (k, v)
                                      for k, v in attrs.items()])


def author_cache_key(m, i, author):
    if IPropertiedUser.providedBy(author) or IMemberData.providedBy(author):
        return author.getId()
    else:
        return author

@ram.cache(author_cache_key)
def readable_ogds_author(item, author):
    if IPropertiedUser.providedBy(author) or IMemberData.providedBy(author):
        author = author.getId()
    info = getUtility(IContactInformation)
    if info.is_user(author) or info.is_contact(author) or info.is_inbox(author):
        return info.describe(author)
    else:
        return author

@ram.cache(author_cache_key)
def linked_ogds_author(item, author):
    if IPropertiedUser.providedBy(author) or IMemberData.providedBy(author):
        author = author.getId()
    info = getUtility(IContactInformation)
    if info.is_user(author) or info.is_contact(author) or info.is_inbox(author):
        return info.render_link(author)
    else:
        return author

def linked(item, value):
    url_method = lambda: '#'
    #item = hasattr(item, 'aq_explicit') and item.aq_explicit or item
    if hasattr(item, 'getURL'):
        url_method = item.getURL
    elif hasattr(item, 'absolute_url'):
        url_method = item.absolute_url
    img = '<img src="%s/%s"/>' % (item.portal_url(),
                                  item.getIcon.encode('utf-8'))

    breadcrumb_titles = []
    for elem in item.breadcrumb_titles:
        if isinstance(elem.get('Title'), unicode):
            breadcrumb_titles.append(elem.get('Title').encode('utf-8'))
        else:
            breadcrumb_titles.append(elem.get('Title'))
    link = '%s&nbsp;<a class="rollover-breadcrumb" href="%s" title="%s">%s</a>' % (
        img, url_method(),
        " &gt; ".join(t for t in breadcrumb_titles),
        value.encode('utf-8'))
    wrapper = '<span class="linkWrapper">%s</span>' % link
    return wrapper

def readable_date_set_invisibles(item, date):
    if not date or str(date) == '1970/01/01' \
            or str(date) == '1970-01-01 00:00:00':
        return u''
    strftimestring = '%d.%m.%Y'
    if date == None:
        return None
    return date.strftime(strftimestring)

def email_helper(item, value):
    if value:
        return '<a href="mailto:%s">%s</a>' % (value, value)
    else:
        return ''


def boolean_helper(item, value):
    """Helper for displaying a boolean field in human readable form.
    """

    return value and _(u'label_yes', default='Yes') or \
                     _(u'label_no', default='No')

def subdossier_helper(content, value):
    """Returns the title of the subdossier the object is contained in, or an empty
    string if the dossier is the root dossier
    """

    obj = content.getObject()
    parent = aq_parent(obj)
    if 'opengever.dossier' in parent.portal_type:
        if 'opengever.dossier' in aq_parent(parent).portal_type:
            # parent is a subdossier
            return parent.Title()
    return ''