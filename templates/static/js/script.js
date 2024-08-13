$(document).ready(function() {
    $.ajax({
        url: "/history",
        method: "GET",
        cache: false
    }).done(function(data) {
        var priceData = [];
        var dates = [];

        for (var i in data.Close) {
            var dt = i.slice(0, i.length - 3);
            var dateString = moment.unix(dt).format("MM/YY");
            var close = data.Close[i];
            if (close != null) {
                priceData.push(data.Close[i]);
                dates.push(dateString);
            }
        }

        Highcharts.chart('chart_container', {
            title: {
                text: 'Finance Chart'
            },
            yAxis: {
                title: {
                    text: ''
                }
            },
            xAxis: {
                categories: dates
            },
            legend: {
                layout: 'vertical',
                align: 'right',
                verticalAlign: 'middle'
            },
            plotOptions: {
                series: {
                    label: {
                        connectorAllowed: false
                    }
                },
                area: {}
            },
            series: [{
                type: 'area',
                color: '#85bb65',
                name: 'Price',
                data: priceData
            }],
            responsive: {
                rules: [{
                    condition: {
                        maxWidth: 640
                    },
                    chartOptions: {
                        legend: {
                            layout: 'horizontal',
                            align: 'center',
                            verticalAlign: 'bottom'
                        }
                    }
                }]
            }
        });
    });
});