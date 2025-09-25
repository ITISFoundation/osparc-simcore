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


qx.Class.define("osparc.support.BookACall", {
  extend: qx.ui.container.Stack,

  construct: function() {
    this.base(arguments);
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "call-topic-selector":
          control = new osparc.support.CallTopicSelector();
          this.getChildControl("main-stack").add(control);
          break;
        case "book-a-call-iframe":
          control = new osparc.wrapper.BookACallIframe();
          this.getChildControl("main-stack").add(control);
          break;
      }
      return control || this.base(arguments, id);
    },
  }
});
