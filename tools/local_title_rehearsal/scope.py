"""Exact rendered-check contract for this one disposable page-title test."""
from dataclasses import asdict
import re

from seo_agent.local_title_rehearsal import transition
from seo_agent.page_tracking import text_value
from seo_agent.post_title_effects import TitleEffect
from seo_agent.publication_verification import Effect

HOME = 'http://127.0.0.1:18718'
PATHS = ('/psychological-assessments-paoli/', '/contact-us/')
CURRENT = 'Comprehensive Psychological Assessments'
PROPOSED = 'Synthetic Local Title Rehearsal 20261117'
HEADING = '[data-id="022c973"] > h1'
BREADCRUMB = '[data-id="2be23dd"] > ul > li:nth-child(2) > a > span.elementor-icon-list-text'
CONTACT_HEADING = '[data-id="c2a3857"] > h1'
NAVIGATION = tuple(
    f'#menu-{instance}-{widget} .menu-item-{item} > a[href="{HOME}{PATHS[0]}"]'
    for widget, item in (('2527b27', '771'), ('5e78af5', '801'))
    for instance in (1, 2)
)
# The retained historical sanitizer omits this disposable port's href values.
# Bind literal locations to exact menu/item identities; raw rules bind URLs.
LITERAL_NAVIGATION = tuple(selector.partition('[href=')[0] for selector in NAVIGATION)


def validate_replacement(value):
    # WordPress's byte bound and the literal and raw rendered verifiers all apply.
    # Exclude text that WordPress typography filters can rewrite on this route.
    if (not isinstance(value, str) or not value or value == CURRENT or text_value(value) != value or
            any(c in '<>&\'"' or ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value) or
            len(value.encode('utf-8')) > 500 or 'Wordpress' in value or
            re.search(r'``|--|(?:^| )-(?: |$)|\.\.\.|\(tm\)|\d+x\d+', value, re.I)):
        raise ValueError('Unsupported local Title text. Use distinct literal text with single spaces and no markup or typography substitutions.')
    return value


def expected_scope(document_titles, *, replacement=PROPOSED):
    """Declare the fixed locations, transitions and unchanged metadata explicitly."""
    validate_replacement(replacement)
    if (not isinstance(document_titles, (list, tuple)) or len(document_titles) != 2 or
            any(not isinstance(title, str) or not title for title in document_titles) or
            not document_titles[0].startswith(CURRENT) or document_titles[0].count(CURRENT) != 1):
        raise ValueError('Two baseline document titles with the expected target title are required')
    suffix = document_titles[0][len(CURRENT):]
    pages = []
    for index, path in enumerate(PATHS):
        literals = [TitleEffect(selector) for selector in LITERAL_NAVIGATION]
        # The publication verifier deliberately treats hidden dropdown ancestors
        # as unavailable. The literal verifier still checks all four instances.
        publication = [Effect(kind='navigation_label', selector=selector, before=CURRENT, after=replacement)
                       for selector in NAVIGATION[::2]]
        if index == 0:
            literals = [TitleEffect('head > title', suffix=suffix), TitleEffect(HEADING),
                        TitleEffect(BREADCRUMB), *literals]
            publication = [Effect(kind='heading', selector=HEADING, before=CURRENT, after=replacement),
                           Effect(kind='breadcrumb', selector=BREADCRUMB, before=CURRENT, after=replacement),
                           *publication]
            after_title = replacement + suffix
        else:
            publication = [Effect(kind='heading', selector=CONTACT_HEADING, before='Contact Us', after='Contact Us'),
                           *publication]
            after_title = document_titles[1]
        publication += [Effect(kind='document_title', before=document_titles[index], after=after_title),
                        Effect(kind='canonical', before=HOME+path, after=HOME+path),
                        Effect(kind='robots', before='noindex, nofollow', after='noindex, nofollow'),
                        Effect(kind='x_robots_tag', before='noindex, nofollow, noarchive', after='noindex, nofollow, noarchive')]
        pages.append({'url': HOME+path, 'title_effects': [asdict(rule) for rule in literals],
                      'publication_effects': [rule.model_dump() for rule in publication]})
    return {'pages': pages}


def validate_scope(declaration, *, document_titles, replacement=PROPOSED):
    """Reject missing/extra pages, locations, rules or values before any write."""
    expected = expected_scope(document_titles, replacement=replacement)
    if (not isinstance(declaration, dict) or set(declaration) != {'pages'} or
            not isinstance(declaration['pages'], list) or len(declaration['pages']) != len(PATHS)):
        raise ValueError('Declare exactly the two fixed pages in capture order')
    normalized = []
    for page in declaration['pages']:
        if (not isinstance(page, dict) or set(page) != {'url', 'title_effects', 'publication_effects'} or
                any(not isinstance(page[key], list) or not page[key]
                    for key in ('title_effects', 'publication_effects'))):
            raise ValueError('Each fixed page requires nonempty literal and publication checks')
        try:
            literals = [TitleEffect(**rule) for rule in page['title_effects']]
            if any(type(rule.count) is not int or not all(isinstance(value, str) for value in
                       (rule.selector, rule.prefix, rule.suffix)) for rule in literals):
                raise ValueError('Invalid literal rule types')
            effects = [Effect.model_validate(rule).model_dump() for rule in page['publication_effects']]
        except (TypeError, ValueError):
            raise ValueError('Malformed title or publication check') from None
        normalized.append({'url': page['url'], 'title_effects': [asdict(rule) for rule in literals],
                           'publication_effects': effects})
    if normalized != expected['pages']:
        raise ValueError('Scope differs from the fixed URLs, locations or expected transitions')
    return {'pages': normalized}


def save_forward(backend, directory, declaration, *, document_titles, binding=None):
    """Scope rejection must occur before invoking even the backend's read method."""
    replacement = binding['replacement'] if binding is not None else PROPOSED
    validate_scope(declaration, document_titles=document_titles, replacement=replacement)
    return transition(backend, directory, 'forward', expected=CURRENT, replacement=replacement, binding=binding)
