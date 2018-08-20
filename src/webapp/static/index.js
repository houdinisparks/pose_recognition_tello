// wait for the DOM to be loaded
$(document).ready(function() {

    // configure te websockets tello state polling
    var socket = io.connect('http://' + document.domain + ':' + location.port);

    function TelloModel(){
        var self = this;
        self.tello_connection = ko.observable();
        self.tello_connection({
            status: "checking",
            color: "badge orange",
            battery: "checking",
            speed: "checking",
            flight_time: "checking",
            battery_color: "badge orange"
        })


        self.update = function(tello_data){
            tello_state = tello_data["tello_state"]
            tello_battery = tello_data["tello_battery"]
            tello_speed = tello_data["tello_speed"]
            tello_flight_time = tello_data["tello_flight_time"]

//            if (tello_state === "disconnected"){
//                self.tello_connection({
//                    status: self.check_status_color(tello_state),
//                    color: "badge red",
//                    battery: tello_battery,
//                    battery_color:self.check_battery_color(tello_battery),
//                    speed: tello_speed,
//                    flight_time: tello_flight_time
//                })
//            }else {
            self.tello_connection({
                status: tello_state,
                color: self.check_status_color(tello_state),
                battery: tello_battery,
                battery_color:self.check_battery_color(tello_battery),
                speed: tello_speed,
                flight_time: tello_flight_time
            })

        }

        self.check_status_color = function(tello_status){
            if (tello_status === "disconnected"){
                return "badge red"
            }else{
                return "badge green"
            }
        }

        self.check_battery_color = function(battery){
            if (battery ==="disconnected"){
                return "badge red"
            }
            else if (battery < 15){
                return "badge orange"
            }else  {
                return "badge green"
            }
        }
    }

    telloModel = new TelloModel()
    ko.applyBindings(telloModel, $("div#tello_connection")[0])

    socket.on("tello_state", function(json_data) {
        console.log('received tello data ' + json_data);
        telloModel.update(json_data)
    });



    $("button#tello_connection_butt").click(function(e){
        e.preventDefault();
        console.log("asd")
        $.ajax({
            type: "POST",
            url: "/connect_tello",
            success: function(result) {
                toastr["success"](result)
            },
            error: function(result) {
                toastr["error"](result.responseText)
            }
        });
    });


    // bind 'myForm' and provide a simple callback function
    $("button#start").click(function(e) {
        e.preventDefault();
        var button = $(this)
        $.ajax({
            type: "POST",
            url: "/start",
            data: {
                server_add:  $('select#server_add').find(":selected").text(), // < note use of 'this' here
            },
            success: function(result) {
                // this part will not load until all data is loaded. therefore it does
                // not work for streaming
//                $("#process_container").text(result)
                toastr["success"](result)
                $("#process_container").prepend('<img id="camera_feed" class="mx-auto d-block" src="/camera_feed' + '?' + Math.random() +'"/>')
                button.prop('disabled' , true)
            },
            error: function(result) {
                toastr["error"]("An error occurred.")
                $("#process_container").text(result)
                if ($('#camera_feed').length > 0){
                    $("#camera_feed").remove()

                }

            }
        });
    });

    $("button#stop").click(function(e) {
        e.preventDefault();
        $.ajax({
            type: "POST",
            url: "/stop",
            data: {
            },
            success: function(result) {
                if ($('#camera_feed').length > 0){
                    $("#camera_feed").remove()
                }
                toastr["success"](result)
                $("button#start").prop('disabled' , false)
            },
            error: function(result) {
                toastr["error"](result)
            }
        });
    });

    function ping(ip, callback) {

        if (!this.inUse) {
            this.status = 'unchecked';
            this.inUse = true;
            this.callback = callback;
            this.ip = ip;
            var _that = this;
            this.img = new Image();
            this.img.onload = function () {
                _that.inUse = false;
                _that.callback('online','badge green');

            };
            this.img.onerror = function (e) {
                if (_that.inUse) {
                    _that.inUse = false;
                    _that.callback('online', 'badge green',e);
                }

            };
            this.start = new Date().getTime();
            this.img.src = "http://" + ip;
            this.timer = setTimeout(function () {
                if (_that.inUse) {
                    _that.inUse = false;
                    _that.callback('offline','badge red');
                }
            }, 1500);
        }
    }

    var PingModel = function () {
        var self = this;

        // self refers to the data bindings. server1 & server2 are contexts
        // initialise
        self.server = {}
//        self.server.name = server
        self.server.status = ko.observable('unchecked')
        self.server.color = ko.observable("badge orange");

        self.update = function(serverip){
//            self.server.name = server
            self.server.status('checking');
            self.server.color('badge orange')

            if(serverip !== ""){
                new ping(serverip, function (status,color, e) {
                    self.server.status(status);
                    self.server.color(color)

                });
            }else{
                self.server.status('offline');
                self.server.color('badge red')
            }

        }
    }

    var pingmodel1 = new PingModel()
    ko.applyBindings(pingmodel1, $("div#server1")[0])
//    var pingmodel2 = new PingModel()
//    ko.applyBindings(pingmodel2, $("div#server2")[0])

    $("button.ping_button").click(function(){

         var server_add_1 = $('select#server_add').find(":selected").text().split(":")[0];
//        var server_add_1 = $("input#server_add").val().split(":")[0]
//        var server_add_2 = $("input#server_add2").val().split(":")[0]

        pingmodel1.update(server_add_1)
//        pingmodel2.update(server_add_2)

    })

    var originalVal;

    $('#res_input').slider().on('slideStart', function(ev){
        originalVal = $('#res_input').data('slider').getValue();
    });

    $('#res_input').slider().on('slideStop', function(ev){
        var newVal = $('#res_input').data('slider').getValue();
        if(originalVal != newVal) {
            // ajax method to change reso of picture

            $.ajax({
                type: "POST",
                url: "/change_reso/"+newVal,
                success: function(result) {
                    toastr["success"](result)
                },
                error: function(result) {
                    toastr["error"](result.responseText)
                }
        });

    }

});


});

