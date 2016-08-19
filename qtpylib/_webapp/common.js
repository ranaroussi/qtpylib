var algos=[], poscount=0, tradecount=0, active_algo='',first=true;

function getTrades(){
    var api_path = (active_algo == '') ? '/trades' : '/algo/'+active_algo;
    $.getJSON(api_path, function(data) {
        $("*[templatejs-rendered=trades]").remove();
        if (data.length>0) {
            $.templateJS('trades', data);
        }
        tradecount = data.length;
    });
};

function getPositions(){
    var api_path = (active_algo == '') ? '/positions' : '/positions/'+active_algo;
    $.getJSON(api_path, function(data) {
        $("*[templatejs-rendered=positions]").remove()
        if (data.length>0) {
            $.templateJS('positions', data);
        }
        poscount = data.length;
    });
}

$(document).ready(function() {

    getPositions();
    getTrades();
    setInterval(function(){
        getPositions();
        getTrades();
    }, 30*1000);


    $.getJSON("/algos", function(data) {
        for (var i = 0; i < data.length; i++) {
            $('#algos').append($('<option/>', {
                value: data[i].name,
                text : data[i].name
            }));
        }
    });

    $("#algos").change(function(){
        if ($(this).val() != active_algo) {
            poscount = 0
            active_algo = $(this).val();
            getPositions();
        }
    });
});