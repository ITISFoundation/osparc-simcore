/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.support.SupportCenter", {
  extend: osparc.ui.window.SingletonWindow,

  construct: function() {
    this.base(arguments, "support-center");

    this.getChildControl("captionbar").exclude();

    this.set({
      layout: new qx.ui.layout.VBox(10),
      contentPadding: 0,
      modal: true,
      clickAwayClose: true,
    });

    this.getChildControl("intro-text");
    this.getChildControl("conversations-list");
  },

  statics: {
    openWindow: function() {
      const supportCenterWindow = new osparc.support.SupportCenter();
      supportCenterWindow.center();
      supportCenterWindow.open();
      return supportCenterWindow;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "stack-layout":
          control = new qx.ui.container.Stack().set({
            padding: 10,
          });
          this._add(control);
          break;
        case "conversations-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this.getChildControl("stack-layout").add(control);
          break;
        case "intro-text":
          control = new qx.ui.basic.Label(this.tr("Welcome to the Support Center"));
          this.getChildControl("conversations-layout").add(control);
          break;
        case "conversations-list": {
          control = new osparc.support.Conversations().set({
            minHeight: 300,
          });
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this.getChildControl("conversations-layout").add(scroll);
          break;
        }
      }
      return control || this.base(arguments, id);
    },
  }
});
