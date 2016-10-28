window.onload = function() {

  // readthedocs
  if (window.location.href.indexOf('en/latest') !== -1) return

  // external links open in new tab
  $("a[href^='http']").attr('target','_blank');

  $("#qtpylib-pythonic-algorithmic-trading p a.reference.external").first().show();
  // $("#qtpylib-pythonic-algorithmic-trading p a.reference.external").not(":eq(0)").hide();

  // own domain?
  var domain = document.domain || '';
  if (domain.indexOf('qtpylib') !== -1) {

    // google analytics
    (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
      (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
      m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
    })(window,document,'script','https://www.google-analytics.com/analytics.js','ga');
    ga('create', 'UA-82818340-1', 'auto');
    ga('send', 'pageview');

    // decorate sidebar
    $('.wy-side-scroll').after('<div id="side-ext"></div>');
    $('#side-ext').append('<a target="_new" download="qtpylib-docs.epub" href="https://github.com/ranaroussi/qtpylib/raw/master/docs/build/epub/QTPyLib.epub" class="fa fa-book">ePub</a>');
    $('#side-ext').append(' &nbsp;|&nbsp; ');
    $('#side-ext').append('<a target="_new" download="qtpylib-docs.zip" href="https://github.com/ranaroussi/qtpylib/raw/master/docs/build/html.zip" class="fa fa-file-archive-o">Zip</a>');
    $('#side-ext').append(' &nbsp; || &nbsp; ');
    $('#side-ext').append('<a target="github" href="https://github.com/ranaroussi/qtpylib" class="fa fa-github">GitHub</a>');
    $('#side-ext').append(' &nbsp;|&nbsp; ');
    $('#side-ext').append('<a target="twitter" href="https://twitter.com/aroussi" class="fa fa-twitter">Twitter</a>');
  }

}