/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global io */

/**
 * @asset(socketio/socket.io.min.js)
 * @ignore(io)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/socketio/socket.io' target='_blank'>WebSocket</a>
 */

qx.Class.define("osparc.wrapper.WebSocket", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "socket.io",
    VERSION: "4.5.4",
    URL: "https://github.com/socketio/socket.io"
  },

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
    "error": "qx.event.type.Data",
    /** socket.io logout event */
    "logout": "qx.event.type.Data"
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
      init: "/",
      check: "String"
    },
    /** The port used to connect */
    port: {
      nullable: true,
      init: null,
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
      init: 10000,
      check: "Number"
    },
    /** Reconnection delay for socket.io. */
    reconnectionDelay: {
      nullable: false,
      init: 500,
      check: "Number"
    },
    /** Max reconnection attempts */
    maxReconnectionAttempts: {
      nullable: false,
      init: 1000,
      check: "Number"
    }
  },

  /** Constructor
   * @param {string} [namespace] The namespace to connect on
   * @returns {void}
   */
  construct(namespace) {
    // this.base();
    if (namespace === undefined) {
      namespace = "app";
    }
    if (namespace) {
      this.setNamespace(namespace);
    }
    this.__name = [];
    this.__cache = {};
  },

  members: {
    // The name store an array of events
    __name: null,
    __cache: null,

    /**
     * Trying to using socket.io to connect and plug every event from socket.io to qooxdoo one
     * @returns {void}
     */
    connect: function() {
      // initialize the script loading
      let socketIOPath = "socketio/socket.io.min.js";
      let dynLoader = new qx.util.DynamicScriptLoader([
        socketIOPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(socketIOPath + " loaded");
        this.setLibReady(true);


        if (this.getSocket() !== null) {
          this.disconnect();
        }

        let dir = this.getUrl();
        if (this.getPort() > 0) {
          dir += ":" + this.getPort();
        }
        console.log("socket in", dir);
        let mySocket = io(dir, {
          "reconnection": this.getReconnect(),
          "timeout": this.getConnectTimeout(),
          "reconnectionDelay": this.getReconnectionDelay(),
          "reconnectionAttempts": this.getMaxReconnectionAttempts(),
          "forceNew": true,
          "query": "client_session_id="+osparc.utils.Utils.getClientSessionID(),
          "transports": ["websocket"]
        });
        this.setSocket(mySocket);

        [
          "connecting",
          "message",
          "close",
          "reconnect",
          "reconnecting",
          "error",
          "logout"
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

    isConnected: function() {
      if (this.getSocket()) {
        return this.getSocket().connected;
      }
      return false;
    },

    disconnect: function() {
      if (this.getSocket() !== null) {
        this.getSocket().removeAllListeners();
        this.getSocket().disconnect();
      }
    },

    /**
     * Emit an event using socket.io
     *
     * @param {string} name The event name to send to Node.JS
     * @param {object} jsonObject The JSON object to send to socket.io as parameters
     * @returns {void}
     */
    emit: function(name, jsonObject) {
      this.getSocket().emit(name, jsonObject);
    },

    /**
     * Connect and event from socket.io like qooxdoo event
     *
     * @param {string} name The event name to watch
     * @param {function} fn The function which will catch event response
     * @param {mixed} that A link to this
     * @returns {void}
     */
    on: function(name, fn, that) {
      this.__name.push(name);
      const socket = this.getSocket();
      if (socket) {
        if (typeof (that) !== "undefined" && that !== null) {
          socket.on(name, qx.lang.Function.bind(fn, that));
        } else {
          socket.on(name, fn);
        }

        // add a duplicated slot listener to keep the messages cached
        socket.on(name, message => {
          if (!(name in this.__cache)) {
            this.__cache[name] = [];
          }
          const info = {
            date: new Date(),
            message: message ? message : "",
          }
          this.__cache[name].unshift(info);
          if (this.__cache[name].length > 20) {
            this.__cache[name].length = 20;
          }
        }, this);
      }
    },

    slotExists: function(name) {
      return this.__name && this.__name.includes(name);
    },

    removeSlot: function(name) {
      let index = this.__name.indexOf(name);
      if (index > -1) {
        this.getSocket().removeAllListeners(this.__name[index]);
        this.__name.splice(index, 1);
        index = this.__name.indexOf(name);
        while (index > -1) {
          this.__name.splice(index, 1);
          index = this.__name.indexOf(name);
        }
      }
    },

    getCachedMessages: function() {
      return this.__cache;
    },
  },

  /**
   * Destructor
   * @returns {void}
   */
  destruct() {
    if (this.getSocket() !== null) {
      // Deleting listeners
      if (this.__name !== null && this.__name.length >= 1) {
        for (let i = 0; i < this.__name.length; ++i) {
          this.getSocket().removeAllListeners(this.__name[i]);
        }
      }
      this.__name = null;
      this.__cache = null;

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
