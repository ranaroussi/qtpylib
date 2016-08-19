//! template.js
//! version : 1.0.1
//! authors : Ran Aroussi
//! license : MIT
//! github.com/tuki/templatejs

;(function(templateJS, window, document, undefined) {

    function isArray(input) {
        return Object.prototype.toString.call(input) === '[object Array]';
    }

    // format number
    function format_number(no, decimals) {
        no = parseFloat(no);
        decimals = (decimals === undefined) ? 2 : decimals;
        no = no.toFixed(decimals) +'';
        x = no.split('.');
        x1 = x[0];
        x2 = x.length > 1 ? '.' + x[1] : '';
        var rgx = /(\d+)(\d{3})/;
        while (rgx.test(x1)) {
            x1 = x1.replace(rgx, '$1' + ',' + '$2');
        }
        return x1 + x2;
    }

    function format_number_as_word(num) {
         if (num >= 1000000000) {
            return (num / 1000000000).toFixed(1).replace(/\.0$/, '') + 'B';
         }
         if (num >= 1000000) {
            return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
         }
         if (num >= 1000) {
            return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
         }
         return num;
    }

    // document ready (pure js)
    function docReady(callback) {
        var addListener    = document.addEventListener    || document.attachEvent,
            removeListener = document.removeEventListener || document.detachEvent,
            eventName      = document.addEventListener ? "DOMContentLoaded" : "onreadystatechange";

        if (document.readyState === "complete" || document.readyState === "loaded" || document.readyState === "interactive") {
            callback(document, event);
            try{ removeListener(eventName, arguments.callee, false); }catch(err){}
            return;
        }
    }

    // --- hide template ---
    try {
        $(document).ready(function() {
            $('*[templatejs]').hide();
        });
    } catch (er) {
        docReady(function() {
            var templates = document.querySelectorAll('*[templatejs]');
            for (var i = 0; i < templates.length; i++) {
                templates[i].style.display = "none";
            }
        });
    }
    // -- /hide template --

    // allowe outside writing of modifiers
    var ext_modifiers = {};
    templateJS.extend = function(modifier, callback) {
        ext_modifiers[modifier] = callback;
    };

    function run_modifiers(value, modifiers, undefined) {
        if (value === '' || value === undefined || value === null) {
            if (modifiers[0] === "allow_null") {
                return '';
            }
            return '-';
        }

        if (!modifiers || modifiers.length == 0) {
            return value;
        }

        value = value.toString();

        for (var i = 0; i < modifiers.length; i++) {
            var modifier = modifiers[i].toLowerCase();

            if (modifier === "capitalize") value = value.toLowerCase().replace(/^.|\s\S/g,function(a){return a.toUpperCase();});
            if (modifier === "uppercase")  value = value.toUpperCase();
            if (modifier === "lowercase")  value = value.toLowerCase();
            if (modifier === "nozero" && value.toString() === "0") value = "";
            if (modifier === "clean_url")  {
                value = value.split("://");
                if (value.length === 2) {
                    value = value[1];
                } else {
                    value = value[0];
                }
                value = value.replace("www.", "");
                if (value.slice(0 -1) == '/') {
                    value = value.substring(0, value.length-1);
                }
            }
            if (modifier === "unix2date")  value = new Date(value*1000)

            if (modifier === "format_number") value = format_number(value, 2);
            if (modifier === "format_decimal") value = format_number(value, 2);
            if (modifier === "format_number_as_word") value = format_number_as_word(value);
            if (modifier === "format_int") value = format_number(value, 0);

            if (modifier === "link") {
                var replacedText, replacePattern1, replacePattern2, replacePattern3;

                // URLs starting with http://, https://, or ftp://
                replacePattern1 = /(\b(https?|ftp):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/gim;
                replacedText = value.replace(replacePattern1, '<a href="$1" target="_blank">$1</a>');

                // URLs starting with "www." (without // before it, or it'd re-link the ones done above).
                replacePattern2 = /(^|[^\/])(www\.[\S]+(\b|$))/gim;
                replacedText = replacedText.replace(replacePattern2, '$1<a href="http://$2" target="_blank">$2</a>');

                // Change email addresses to mailto:: links.
                replacePattern3 = /(([a-zA-Z0-9\-\_\.])+@[a-zA-Z\_]+?(\.[a-zA-Z]{2,6})+)/gim;
                replacedText = replacedText.replace(replacePattern3, '<a href="mailto:$1">$1</a>');

                value = replacedText;
            }

            // external modifiers
            if (ext_modifiers.hasOwnProperty(modifier)) {
                value = ext_modifiers[modifier](value);
            }
        };

        // return
        return value;
    }

    function single(template, data) {
        return template.replace(/\{([\w\|\.]*)\}/g, function(str, raw_key) {
            var key = raw_key.split('|')[0];

            var modifiers = raw_key.split('|').splice(1);

            var keys = key.split(".");
            var values = data[keys.shift()];

            // nested items
            for (var i = 0, l = keys.length; i < l; i++) {
                values = values[keys[i]];
            }

            // pass through modifiers
            values = run_modifiers(values, modifiers);

            return (typeof values !== "undefined" && values !== null) ? values : "";
        });
    }

    function loop(template, data) {
        var template_items = [];
        for (var i = 0; i < data.length; i++) {
            template_items.push(single(template, data[i]));
        }
        return template_items;
    }

    templateJS.parse = function(templateId, data, callback){

        // read template element
        // var template_obj = $('*[templatejs='+templateId+']')[0];
        var template_obj = document.querySelectorAll('*[templatejs='+templateId+']')[0]
        if (!template_obj) return;

        // show template element
        // $('*[templatejs='+templateId+']').first().show();
        document.querySelectorAll('*[templatejs='+templateId+']')[0].style.display = "";

        // remove previously rendered template
        var rendered = document.querySelectorAll('*[templatejs-rendered='+templateId+']');
        for (var i = 0; i < rendered.length; i++) {
            rendered[i].parentNode.removeChild(rendered[i]);
        };

        // get template html from template element
        var template_html = template_obj.outerHTML
            .replace('templatejs="'+ templateId +'"', 'templatejs-rendered="'+ templateId +'"')
            .replace("templatejs='"+ templateId +"'", 'templatejs-rendered="'+ templateId +'"');

        // parse html container
        var parsed_html = '';

        // data must be an array
        if (!isArray(data)) data = [data];

        // parse
        if (data.length <= 1) {
            parsed_html = single(template_html, data[0]);
        } else {
            parsed_html = loop(template_html, data);
        }

        // add to template element
        $(template_obj).before(parsed_html);

        // activate tooltip for bootstrap
        try {
            $('*[data-toggle="tooltip"]').tooltip();
        } catch(er){}

        // prevent linkage for pretty-select
        try {
            prettySelect.renderLinks();
        } catch(er){}

        // remove template element
        // $(template_obj).remove();

        // hide template element (for future use)
        document.querySelectorAll('*[templatejs='+templateId+']')[0].style.display = "none";

        try{ callback(); } catch(er){}
    };

}(window.templateJS = window.templateJS || {}, window, document));

// extend jquery
try {
    jQuery.extend({ "templateJS": function(templateId, data, callback) {
        return templateJS.parse(templateId, data, callback);
    }});
} catch(er) {}