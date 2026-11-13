// UUEstrie — language switcher, mobile menu, and hiding events that have passed.
(function () {
  var root = document.documentElement;

  function setLang(lang) {
    if (lang !== 'en' && lang !== 'fr') lang = 'en';
    root.setAttribute('data-lang', lang);
    root.setAttribute('lang', lang === 'fr' ? 'fr' : 'en');
    try { localStorage.setItem('uue-lang', lang); } catch (e) {}
    document.querySelectorAll('[data-set-lang]').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-set-lang') === lang ? 'true' : 'false');
    });
  }
  setLang(root.getAttribute('data-lang'));
  document.querySelectorAll('[data-set-lang]').forEach(function (b) {
    b.addEventListener('click', function () { setLang(b.getAttribute('data-set-lang')); });
  });

  // "Weekly email" in the header: jump to the footer sign-up form and put the cursor in it.
  document.querySelectorAll('[data-signup]').forEach(function (a) {
    a.addEventListener('click', function (ev) {
      var input = document.getElementById('nl-email');
      var form = document.getElementById('newsletter');
      if (!input || !form) return;
      ev.preventDefault();
      if (nav) nav.classList.remove('open');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
      form.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(function () { input.focus({ preventScroll: true }); }, 400);
      form.classList.add('flash');
      setTimeout(function () { form.classList.remove('flash'); }, 2000);
    });
  });

  var toggle = document.querySelector('.menu-toggle');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  // The site is rebuilt weekly, but in case it isn't, hide events that are over.
  var now = Date.now();
  document.querySelectorAll('.upcoming [data-end], .coming-soon [data-end]').forEach(function (el) {
    var end = Date.parse(el.getAttribute('data-end'));
    if (!isNaN(end) && end < now) el.remove();
  });
  document.querySelectorAll('.upcoming').forEach(function (list) {
    var first = list.querySelector('.card');
    if (list.querySelector('.card.big') === null && first && list.closest('.hero, section')) {
      if (document.body.querySelector('.hero')) first.classList.add('big');
    }
  });
  document.querySelectorAll('.coming-soon').forEach(function (cs) {
    if (!cs.querySelector('li')) cs.remove();
  });
})();
