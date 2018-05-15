/**
 * Creates a standard widget for a login
 *
 *  Features:
 *    - Login form
 *    - Some decoration
 *
 */

/* eslint no-warning-comments: "off" */

qx.Class.define("qxapp.components.login.Standard", {

  extend: qx.ui.container.Composite,

  /*
  *****************************************************************************
     CONSTRUCTOR
  *****************************************************************************
  */
  construct: function() {
    this.base(arguments);

    let header = this.__createHeader();
    this.__form = new qxapp.components.login.Form();

    // TODO : add Forgot Password? | Create Account? links
    let footer = new qx.ui.core.Widget();

    this.__createLayout(header,
      new qx.ui.form.renderer.Single(this.__form),
      footer);

    this.__form.addListener("submit", this.__onSubmitLogin, this);
  },

  /*
   *****************************************************************************
      MEMBERS
   *****************************************************************************
   */
  members: {
    __form: null,
    __token: null,
    __info: null,

    __createHeader: function() {
      // const isDev = Boolean(qx.core.Environment.get("qx.debug"));

      // TODO: bind label and icon to this property

      let header = new qx.ui.basic.Atom().set({
        icon: "qxapp/itis-white.png",
        iconPosition: "top"
      });

      return header;
    },

    __createLayout: function(header, login, footer) {
      // http://www.qooxdoo.org/5.0.2/pages/desktop/ui_layouting.html
      // http://www.qooxdoo.org/5.0.2/pages/layout.html
      // http://www.qooxdoo.org/5.0.2/pages/layout/box.html
      // http://www.qooxdoo.org/5.0.2/demobrowser/#layout~VBox.html

      // const isDev = Boolean(qx.core.Environment.get("qx.debug"));

      // LayoutItem
      this.set({
        padding: 10
      });

      this.setLayoutProperties({
        allowGrowY: false
      });

      /*
      login.set({
        // backgroundColor: isDev ? "red" : null,
        // width: 100 // TODO: themed?
      });

      // Set buttom wider
      login.getLayout().set({
        // spacingY: 10 // TODO: themed?
      });

      footer.set({
        // backgroundColor: isDev ? "blue" : null
      });
      */

      // Children's layout management
      let layout = new qx.ui.layout.VBox().set({
        alignY: "middle",
        spacing: 20 // TODO: themed?
      });
      this.setLayout(layout);


      // Example of item properties {flex:0, width='%'} passed as options.
      // notice that these options are specific for every layout abstraction!
      // the he uses the api LayoutItem.setLayoutProperties to set computed layout
      // considering parent layout hints
      this.add(header);
      this.add(login);
      // this.add(footer);
    },

    __onSubmitLogin: function(e) {
      // this is user's input
      var loginData = e.getData();

      let auth = new qx.io.request.authentication.Basic(
        loginData.user,
        loginData.password);

      // TODO: encapsulate entire request in separate class
      // let req = new qxapp.io.request.Login(loginData());

      // let serializer = function (object) {
      //  if (object instanceof qx.ui.form.ListItem) {
      //    return object.getLabel();
      //  }
      // };
      // console.debug("You are sending: " +
      //  qx.util.Serializer.toUriParameter(model, serializer));

      // Requests authentication to server
      let req = new qx.io.request.Xhr();
      req.set({
        // qx.io.request.authentication sets headers.
        // Can send user+passorwd or user=token w/o password!?
        authentication: auth,
        url: "/login",
        method: "POST",
        requestData: qx.util.Serializer.toJson(loginData)
      });

      req.addListener("success", this.__onLoginSucceed, this);
      req.addListener("fail", this.__onLoginFailed, this);
      req.send();
    },

    __onLoginSucceed: function(e) {
      let req = e.getTarget();
      console.debug("Everything went fine!!");
      console.debug("status  :", req.getStatus());
      console.debug("phase   :", req.getPhase());
      console.debug("response: ", req.getResponse());

      this.__info = req.getResponse();
      this.__token = req.getResponse().userToken;

      // TODO: implement token-based authentication: we can request token and from that moment on,
      // just use that...

      // TODO: fire success logged in and store token??
      this.fireDataEvent("login", true);
    },

    __onLoginFailed: function(e) {
      // Display error page!
      let req = e.getTarget();
      console.debug("Something went wrong!!");
      console.debug("status  :", req.getStatus());
      console.debug("phase   :", req.getPhase());
      console.debug("response: ", req.getResponse());

      // TODO: invalidate form view and flash error!
      this.fireDataEvent("login", false);
    }

  },

  /*
  *****************************************************************************
   EVENTS
  *****************************************************************************
  */
  events: {
    "login": "qx.event.type.Data"
  }

});
