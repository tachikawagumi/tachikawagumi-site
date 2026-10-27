(() => {
  'use strict';
  // Only fixed service labels are used in analytics; no form values or URL text.
  const labels = {factory:'工場改修・補修', 'sound-barrier':'高速道路・遮音壁工事', fence:'工事について', general:'工事について'};
  const allowed = value => Object.prototype.hasOwnProperty.call(labels, value);
  const query = new URLSearchParams(window.location.search).get('service');
  const pageService = document.body.dataset.service || 'general';
  const sourceService = allowed(query) ? query : allowed(pageService) ? pageService : 'general';
  const category = document.querySelector('select[name="category"]');
  if (category && allowed(query)) {
    Array.from(category.options).forEach(option => { option.defaultSelected = option.value === labels[query]; });
    category.value = labels[query];
  }
  const sourceField = document.querySelector('input[name="source_service"]');
  if (sourceField) sourceField.value = sourceService;
  const track = (event, service, extra = {}) => {
    if (typeof window.gtag === 'function') window.gtag('event', event, {service:allowed(service) ? service : 'general', ...extra});
  };
  const locationFor = link => link.closest('.mobile-contact-bar') ? 'mobile_bar' : link.closest('header') ? 'header' : link.closest('footer') ? 'footer' : 'content';
  document.querySelectorAll('a[href]').forEach(link => {
    const url = new URL(link.href, window.location.href);
    if (url.protocol === 'tel:') {
      link.addEventListener('click', () => track('phone_click', sourceService, {link_location:locationFor(link)}));
    } else if (url.origin === window.location.origin && url.hash === '#contact') {
      const requested = url.searchParams.get('service');
      link.addEventListener('click', () => track('contact_click', allowed(requested) ? requested : sourceService, {link_location:locationFor(link)}));
    }
  });
  window.tachikawaTrackLead = () => {
    const selected = category?.value === labels.factory ? 'factory' : category?.value === labels['sound-barrier'] ? 'sound-barrier' : 'general';
    track('generate_lead', selected, {source_service:sourceService});
  };
})();
