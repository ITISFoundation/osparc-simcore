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
    this.base(arguments);

    this.set({
      layout: qx.ui.container.Stack,
    });

    this.getChildControl("intro-text");
    this.getChildControl("conversations-list");
  },

  statics: {
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "conversations-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
          this.add(control);
        case "intro-text":
          control = new qx.ui.basic.Label(this.tr("Welcome to the Support Center"));
          this.getChildControl("conversations-layout").add(control);
          break;
        case "conversations-list":
          const control = new osparc.support.Conversations();
          const scroll = new qx.ui.container.Scroll();
          scroll.add(control);
          this.getChildControl("conversations-layout").add(scroll);
          break;
      }
      return control || this.base(arguments, id);
    },
  }
});
