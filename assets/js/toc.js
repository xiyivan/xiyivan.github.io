(function () {
  'use strict';

  function buildTOC() {
    var content = document.querySelector('.post-content');
    if (!content) return;

    var tocList = document.querySelector('.toc-list');
    if (!tocList) return;

    // Get all h1, h2, h3 headings inside post content
    var headings = content.querySelectorAll('h1, h2, h3');
    if (headings.length === 0) {
      var sidebar = document.querySelector('.toc-sidebar');
      if (sidebar) sidebar.style.display = 'none';
      return;
    }

    var currentH2Item = null;

    headings.forEach(function (heading) {
      var tag = heading.tagName.toLowerCase();
      var id = heading.id || generateId(heading);
      if (!heading.id) heading.id = id;

      var link = document.createElement('a');
      link.className = 'toc-link toc-' + tag;
      link.href = '#' + id;
      link.textContent = heading.textContent;

      link.addEventListener('click', function (e) {
        e.preventDefault();
        var target = document.getElementById(id);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          history.pushState(null, null, '#' + id);
        }
      });

      var li = document.createElement('li');
      li.appendChild(link);

      if (tag === 'h1') {
        tocList.appendChild(li);
        currentH2Item = null;
      } else if (tag === 'h2') {
        tocList.appendChild(li);
        currentH2Item = li;
      } else if (tag === 'h3') {
        // Nest h3 under the most recent h2
        if (currentH2Item) {
          var subList = currentH2Item.querySelector('ul');
          if (!subList) {
            subList = document.createElement('ul');
            subList.className = 'toc-sub';
            currentH2Item.appendChild(subList);
          }
          subList.appendChild(li);
        } else {
          // No preceding h2 — append directly to main list
          tocList.appendChild(li);
        }
      }
    });

    setupScrollSpy(headings);
  }

  function generateId(heading) {
    return heading.textContent
      .toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .trim();
  }

  function setupScrollSpy(headings) {
    var tocLinks = document.querySelectorAll('.toc-link');
    if (tocLinks.length === 0) return;

    var observer = new IntersectionObserver(
      function (entries) {
        // Find the topmost heading currently intersecting the viewport
        var topEntry = null;
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            if (
              !topEntry ||
              entry.boundingClientRect.top < topEntry.boundingClientRect.top
            ) {
              topEntry = entry;
            }
          }
        });

        if (topEntry) {
          var id = topEntry.target.id;
          tocLinks.forEach(function (link) {
            link.classList.remove('active');
          });
          var activeLink = document.querySelector(
            '.toc-link[href="#' + CSS.escape(id) + '"]'
          );
          if (activeLink) {
            activeLink.classList.add('active');
          }
        }
      },
      {
        rootMargin: '-80px 0px -60% 0px',
        threshold: 0
      }
    );

    headings.forEach(function (heading) {
      observer.observe(heading);
    });
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildTOC);
  } else {
    buildTOC();
  }
})();
