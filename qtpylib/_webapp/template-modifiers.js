templateJS.extend('quick_state_tooltip', function(val) {
    if (val == 'up') {
        return "Up from prior day";
    }
    else if (val == 'down') {
        return "Down from prior day";
    }
    return 'Same as prior day';
});

templateJS.extend('checked', function(val) {
    if (val == true || val == 'true' || val == 1) {
        return " checked";
    }
    return '';
});

templateJS.extend('first_char', function(val) {
    return val[0];
});
templateJS.extend('nozero', function(val) {
    return (val==0)?'-':val;
});

templateJS.extend('pos_status', function(val) {
    return (val=='')?'active':'completed';
});
templateJS.extend('pnl_status', function(val) {
    return (val==0)?'':((val>0)?'positive':'negative');
});

templateJS.extend('uncamel', function(val) {
    return val.replace(/([A-Z])/g, ' $1')
        // uppercase the first character
        .replace(/^./, function(str){ return str.toUpperCase(); })
});

templateJS.extend('finshort', function(val) {
    return val.toUpperCase().replace('MARKET', 'MKT')
        .replace('LIMIT', 'LMT').replace('STOP', 'STP')
        .replace('TARGET', 'TGT').replace('SIGNAL', 'SGL')
        .replace('LONG', 'LNG').replace('SHORT', 'SRT');
});

templateJS.extend('unix2day', function(val) {
    if (val > 999999999999) val = val/1000
    return moment.unix(val).format('D MMMM, YYYY');
});

templateJS.extend('unix2date', function(val) {
    if (val > 999999999999) val = val/1000
    if (val < 0) return '-'
    return moment.unix(val).format('DD-MMM HH:mm:ss ZZ');
});

templateJS.extend('unix2shortdate', function(val) {
    if (val > 999999999999) val = val/1000
    return moment.unix(val).format('D MMM, YYYY');
});

templateJS.extend('unix2shortday', function(val) {
    if (val > 999999999999) val = val/1000
    return moment.unix(val).format('D MMM');
});