// wait for the DOM to be loaded
$(document).ready(function() {

    // configure te websockets tello state polling
    var socket = io.connect('http://' + document.domain + ':' + location.port);

    function TelloModel(){
        var self = this;
        self.tello_connection = ko.observable();
        self.tello_connection({
            status: "checking",
            color: "badge orange"
        })


        self.update = function(tello_state){
            if (tello_state === "disconnected"){
                self.tello_connection({
                    status: "disconnected",
                    color: "badge red"
                })
            }else if (tello_state === "connected"){
                self.tello_connection({
                    status:"connected",
                    color: " badge green"
                })
            }
        }
    }

    telloModel = new TelloModel()
    ko.applyBindings(telloModel, $("div#tello_connection")[0])

    socket.on("tello_state", function(json_data) {
        console.log('received tello state ' + json_data["tello_state"]);
        telloModel.update(json_data["tello_state"])
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
                server_add: $("input#server_add").val(), // < note use of 'this' here
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

    var PingModel = function (server) {
        var self = this;

        // self refers to the data bindings. server1 & server2 are contexts
        // initialise
        self.server = {}
        self.server.name = server
        self.server.status = ko.observable('unchecked')
        self.server.color = ko.observable("badge orange");

        self.update = function(server){
            self.server.name = server
            self.server.status('checking');
            self.server.color('badge orange')

            if(self.server.name !== ""){
                new ping(self.server.name, function (status,color, e) {
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
    var pingmodel2 = new PingModel()
    ko.applyBindings(pingmodel2, $("div#server2")[0])

    $("button.ping_button").click(function(){

        var server_add_1 = $("input#server_add").val().split(":")[0]
        var server_add_2 = $("input#server_add2").val().split(":")[0]

        pingmodel1.update(server_add_1)
        pingmodel2.update(server_add_2)

    })


});

