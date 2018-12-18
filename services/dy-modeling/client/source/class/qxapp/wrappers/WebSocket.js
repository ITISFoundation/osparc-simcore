/**
 * This class is a direct link with socketio.
 * @asset(socketio/socket.io.js)
 * @ignore(io)
 */

/* global window */
/* global io */

qx.Class.define("qxapp.wrappers.WebSocket", {
  extend: qx.core.Object,

  // Socket.io events
  events: {
    /** socket.io connect event */
    "connect": "qx.event.type.Event",
    /** socket.io connecting event */
    "connecting": "qx.event.type.Data",
    /** socket.io connect_failed event */
    "connect_failed": "qx.event.type.Event",
    /** socket.io message event */
    "message": "qx.event.type.Data",
    /** socket.io close event */
    "close": "qx.event.type.Data",
    /** socket.io disconnect event */
    "disconnect": "qx.event.type.Event",
    /** socket.io reconnect event */
    "reconnect": "qx.event.type.Data",
    /** socket.io reconnecting event */
    "reconnecting": "qx.event.type.Data",
    /** socket.io reconnect_failed event */
    "reconnect_failed": "qx.event.type.Event",
    /** socket.io error event */
    "error": "qx.event.type.Data"
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    },

    /**
     * The url used to connect to socket.io
     */
    url: {
      nullable: false,
      init: "http://".concat(window.location.hostname),
      check: "String"
    },
    pathname: {
      nullable: false,
      init: window.location.pathname,
      check: "String"
    },
    /** The port used to connect */
    port: {
      nullable: false,
      init: Number(window.location.port),
      check: "Number"
    },
    /** The namespace (socket.io namespace), can be empty */
    namespace: {
      nullable: true,
      init: "",
      check: "String"
    },
    /** The socket (socket.io), can be null */
    socket: {
      nullable: true,
      init: null,
      check: "Object"
    },
    /** Parameter for socket.io indicating if we should reconnect or not */
    reconnect: {
      nullable: true,
      init: true,
      check: "Boolean"
    },
    connectTimeout: {
      nullable: true,
      init: 40000,
      check: "Number"
    },
    /** Reconnection delay for socket.io. */
    reconnectionDelay: {
      nullable: false,
      init: 500,
      check: "Number"
    },
    /** Max reconnection attemps */
    maxReconnectionAttemps: {
      nullable: false,
      init: 1000,
      check: "Number"
    }
  },

  /** Constructor
   *
   * @param namespace {string ? null} The namespace to connect on
   */
  construct: function(namespace) {
    this.base(arguments);
    // if (namespace !== null) {
    if (namespace) {
      this.setNamespace(namespace);
    }
    this.__name = [];
  },

  members: {
    // The name store an array of events
    __name: null,

    /**
     * Trying to using socket.io to connect and plug every event from socket.io to qooxdoo one
     */
    connect: function() {
      // initialize the script loading
      let socketIoPath = "socketio/socket.io.js";
      let dynLoader = new qx.util.DynamicScriptLoader([
        socketIoPath
      ]);

      dynLoader.addListenerOnce("ready", function(e) {
        console.log(socketIoPath + " loaded");
        this.setLibReady(true);


        if (this.getSocket() !== null) {
          this.getSocket().removeAllListeners();
          this.getSocket().disconnect();
        }

        let dir = this.getUrl() + ":" + this.getPort();
        console.log("socket in", dir);
        let mySocket = io.connect(dir, {
          "port": this.getPort(),
          "reconnect": this.getReconnect(),
          "connect timeout": this.getConnectTimeout(),
          "reconnection delay": this.getReconnectionDelay(),
          "max reconnection attempts": this.getMaxReconnectionAttemps(),
          "force new connection": true,
          "path": this.getPathname() + "socket.io"
        });
        this.setSocket(mySocket);

        [
          "connecting",
          "message",
          "close",
          "reconnect",
          "reconnecting",
          "error"
        ].forEach(event => {
          this.on(event, ev => {
            this.fireDataEvent(event, ev);
          }, this);
        }, this);

        [
          "connect",
          "connect_failed",
          "disconnect",
          "reconnect_failed"
        ].forEach(event => {
          this.on(event, () => {
            this.fireDataEvent(event);
          }, this);
        }, this);
      }, this);

      dynLoader.start();
    },

    /**
     * Emit an event using socket.io
     *
     * @param name {string} The event name to send to Node.JS
     * @param jsonObject {object} The JSON object to send to socket.io as parameters
     */
    emit: function(name, jsonObject) {
      console.log("emit", name);
      this.getSocket().emit(name, jsonObject);
    },

    /**
     * Connect and event from socket.io like qooxdoo event
     *
     * @param name {string} The event name to watch
     * @param fn {function} The function wich will catch event response
     * @param that {mixed} A link to this
     */
    on: function(name, fn, that) {
      this.__name.push(name);
      if (typeof (that) !== "undefined" && that !== null) {
        this.getSocket().on(name, qx.lang.Function.bind(fn, that));
      } else {
        this.getSocket().on(name, fn);
      }
    },

    slotExists: function(name) {
      for (let i = 0; i < this.__name.length; ++i) {
        if (this.__name[i] === name) {
          return true;
        }
      }
      return false;
    }
  },

  /**
   * Destructor
   */
  destruct: function() {
    if (this.getSocket() !== null) {
      // Deleting listeners
      if (this.__name !== null && this.__name.length >= 1) {
        for (let i = 0; i < this.__name.length; ++i) {
          this.getSocket().removeAllListeners(this.__name[i]);
        }
      }
      this.__name = null;

      this.removeAllBindings();

      // Disconnecting socket.io
      try {
        this.getSocket().socket.disconnect();
      } catch (e) {}

      try {
        this.getSocket().disconnect();
      } catch (e) {}

      this.getSocket().removeAllListeners("connect");
      this.getSocket().removeAllListeners("connecting");
      this.getSocket().removeAllListeners("connect_failed");
      this.getSocket().removeAllListeners("message");
      this.getSocket().removeAllListeners("close");
      this.getSocket().removeAllListeners("disconnect");
      this.getSocket().removeAllListeners("reconnect");
      this.getSocket().removeAllListeners("reconnecting");
      this.getSocket().removeAllListeners("reconnect_failed");
      this.getSocket().removeAllListeners("error");
    }
  }
});
