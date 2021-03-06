from Products.CMFCore.utils import getToolByName
from Products.statusmessages.interfaces import IStatusMessage
from email import Encoders
from email.Header import Header
from email.MIMEBase import MIMEBase
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import formatdate
from five import grok
from ftw.mail.mail import IMail
from opengever.base.source import DossierPathSourceBinder
from opengever.mail import _
from opengever.mail.behaviors import ISendableDocsContainer
from opengever.mail.events import DocumentSent
from opengever.mail.interfaces import ISendDocumentConf
from opengever.mail.validators import AddressValidator
from opengever.mail.validators import DocumentSizeValidator
from opengever.ogds.base.interfaces import IContactInformation
from opengever.ogds.base.utils import get_current_client
from opengever.tabbedview.utils import get_containg_document_tab_url
from plone.directives.form import default_value
from plone.formwidget.autocomplete import AutocompleteMultiFieldWidget
from plone.registry.interfaces import IRegistry
from plone.z3cform import layout
from plone.z3cform.textlines.textlines import TextLinesFieldWidget
from z3c.form import form, button, field, validator
from z3c.form.browser.checkbox import SingleCheckBoxFieldWidget
from z3c.form.interfaces import INPUT_MODE
from z3c.relationfield.schema import RelationChoice, RelationList
from zope import schema
from zope.component import getUtility, provideAdapter
from zope.event import notify
from zope.i18n import translate
from zope.interface import Interface
from zope.interface import invariant, Invalid

CHARSET = 'utf-8'


class NoMail(Invalid):
    """ The No Mail was defined Exception."""
    __doc__ = _(u"No Mail Address")


class ISendDocumentSchema(Interface):
    """ The Send Document Form Schema."""

    intern_receiver = schema.Tuple(
        title=_('intern_receiver', default="Intern receiver"),
        description=_('help_intern_receiver',
                      default="Live Search: search for users and contacts"),

        value_type=schema.Choice(
            title=_(u"mails"),
            source=u'opengever.ogds.base.EmailContactsAndUsersVocabulary'),
        required=False,
        missing_value=(),  # important!
        )

    extern_receiver = schema.List(
        title=_('extern_receiver', default="Extern receiver"),
        description=_('help_extern_receiver',
                      default="email addresses of the receivers. " +
                          "Enter manually the addresses, one per each line."),
        value_type=schema.TextLine(title=_('receiver'), ),
        required=False,
        )

    subject = schema.TextLine(
        title=_(u'label_subject', default=u'Subject'),
        description=_(u'help_subject', default=u''),
        required=True,
        )

    message = schema.Text(
        title=_(u'label_message', default=u'Message'),
        description=_(u'help_message', default=u''),
        required=True,
        )

    documents = RelationList(
        title=_(u'label_documents', default=u'Documents'),
        default=[],
        value_type=RelationChoice(
            title=u"Documents",
            source=DossierPathSourceBinder(
                portal_type=("opengever.document.document", "ftw.mail.mail"),
                navigation_tree_query={
                    'object_provides':
                        ['opengever.dossier.behaviors.dossier.IDossierMarker',
                         'opengever.task.task.ITask',
                         'opengever.document.document.IDocumentSchema',
                         'ftw.mail.mail.IMail',
                         ]}),
            ),
        required=False,
        )

    documents_as_links = schema.Bool(
        title=_(u'label_documents_as_link',
                default=u'Send documents only als links'),
        required=True,
        )

    @invariant
    def validateHasEmail(self):
        """ check if minium one e-mail-address is given."""
        if len(self.intern_receiver) == 0 and not self.extern_receiver:
            raise NoMail(_(u'You have to select a intern \
                            or enter a extern mail-addres'))


@default_value(field=ISendDocumentSchema['documents_as_links'])
def default_documents_as_links(data):
    """Set the client specific default (configured in the registry)."""

    registry = getUtility(IRegistry)
    proxy = registry.forInterface(ISendDocumentConf)
    return proxy.documents_as_links_default


# put the validators
validator.WidgetValidatorDiscriminators(
    DocumentSizeValidator,
    field=ISendDocumentSchema['documents'],
    )

validator.WidgetValidatorDiscriminators(
    AddressValidator,
    field=ISendDocumentSchema['extern_receiver'],
    )

provideAdapter(DocumentSizeValidator)
provideAdapter(AddressValidator)


class SendDocumentForm(form.Form):
    """ The Send Documents per Mail Formular """

    fields = field.Fields(ISendDocumentSchema)
    ignoreContext = True
    label = _('heading_send_as_email', default="Send as email")

    fields['extern_receiver'].widgetFactory[INPUT_MODE] \
        = TextLinesFieldWidget
    fields['intern_receiver'].widgetFactory[INPUT_MODE] \
        = AutocompleteMultiFieldWidget
    fields['documents_as_links'].widgetFactory[INPUT_MODE] \
        = SingleCheckBoxFieldWidget

    def update(self):
        """ put default value for documents field, into the request,

        because this view would call from the document tab in the dossier view

        """
        paths = self.request.get('paths', [])
        if paths:
            self.request.set('form.widgets.documents', paths)
        super(SendDocumentForm, self).update()

    @button.buttonAndHandler(_(u'button_send', default=u'Send'))
    def send_button_handler(self, action):
        """ create and Send the Email """
        data, errors = self.extractData()

        if len(errors) == 0:
            mh = getToolByName(self.context, 'MailHost')
            contact_info = getUtility(IContactInformation)
            userid = self.context.portal_membership.getAuthenticatedMember()
            userid = userid.getId()
            intern_receiver = []
            for receiver in data.get('intern_receiver', []):
                # cut away the username
                intern_receiver.append(receiver.split(':')[0])

            extern_receiver = data.get('extern_receiver') or []
            addresses = intern_receiver + extern_receiver

            # create the mail
            msg = self.create_mail(
                data.get('message'),
                data.get('documents'),
                only_links=data.get('documents_as_links'))

            msg['Subject'] = Header(data.get('subject'), CHARSET)
            sender_address = contact_info.get_email(userid)
            if not sender_address:
                portal = self.context.portal_url.getPortalObject()
                sender_address = portal.email_from_address

            mail_from = '%s <%s>' % (
                    contact_info.describe(userid).encode(CHARSET),
                    sender_address.encode(CHARSET))

            msg['From'] = Header(mail_from, CHARSET)

            header_to = Header(','.join(addresses), CHARSET)
            msg['To'] = header_to

            # send it
            mh.send(msg, mfrom=mail_from, mto=','.join(addresses))

            # let the user know that the mail was sent
            info = _(u'info_mails_sent', 'Mails sent')
            notify(DocumentSent(
                    self.context, userid, header_to, data.get('subject'),
                    data.get('message'), data.get('documents')))

            IStatusMessage(self.request).addStatusMessage(info, type='info')
            # and redirect to default view / tab
            return self.request.RESPONSE.redirect(
                get_containg_document_tab_url(data.get('documents')[0]))

    @button.buttonAndHandler(_('cancel_back', default=u'Cancel'))
    def cancel_button_handler(self, action):
        data, errors = self.extractData()

        if data.get('documents'):
            url = get_containg_document_tab_url(data.get('documents')[0])
        else:
            url = get_containg_document_tab_url(self.context)

        return self.request.RESPONSE.redirect(url)

    def create_mail(self, text='', objs=[], only_links=''):
        """Create the mail and attach the the files. For object without a file
        it include a Link to the Object in to the message"""
        attachment_parts = []
        msg = MIMEMultipart()
        msg['Date'] = formatdate(localtime=True)

        # iterate over object list (which can include documents and mails),
        # create attachement parts for them and prepare docs_links
        docs_links = '%s:\r\n' % (translate(
                _('label_documents', default=u'Documents'),
                context=self.request))

        for obj in objs:

            if IMail.providedBy(obj):
                obj_file = obj.message
            else:
                obj_file = obj.file

            if only_links or not obj_file:

                # rewrite the url with clients public url
                url = '%s/%s' % (
                    get_current_client().public_url,
                    '/'.join(obj.getPhysicalPath()[2:]))

                docs_links = '%s\r\n - %s (%s)' % (
                    docs_links, obj.title, url)
                continue

            docs_links = '%s\r\n - %s (%s)' % (
                docs_links,
                obj.title,
                translate(
                    _('label_see_attachment', default=u'see attachment'),
                    context=self.request))

            mimetype = obj_file.contentType
            if not mimetype:
                mimetype = 'application/octet-stream'
            maintype, subtype = obj_file.contentType.split('/', 1)
            part = MIMEBase(maintype, subtype)
            part.set_payload(obj_file.data)
            Encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"'
                            % obj_file.filename)
            attachment_parts.append(part)

        # First, create the text part and attach it to the message ...
        text = '%s\r\n\r\n%s\r\n' % (
            text.encode(CHARSET, 'ignore'),
            docs_links.encode(CHARSET))

        if not isinstance(text, unicode):
            text = text.decode('utf8')
        msg.attach(MIMEText(text, 'plain', CHARSET))

        # ... then attach all the attachment parts
        for part in attachment_parts:
            msg.attach(part)

        return msg


class SendDocumentFormView(layout.FormWrapper, grok.View):
    """ The View wich display the SendDocument-Form.

    For sending documents with per mail.

    """

    grok.context(ISendableDocsContainer)
    grok.name('send_documents')
    grok.require('zope2.View')
    form = SendDocumentForm

    def __init__(self, context, request):
        layout.FormWrapper.__init__(self, context, request)
        grok.View.__init__(self, context, request)
