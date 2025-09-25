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

    this.__buildLayout();
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "call-topic-selector":
          control = new osparc.support.CallTopicSelector();
          this.add(control);
          break;
        case "book-a-call-iframe":
          control = new osparc.wrapper.BookACallIframe();
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const callTopicSelector = this.getChildControl("call-topic-selector");
      this.setSelection([callTopicSelector]);
      callTopicSelector.addListener("nextPressed", e => {
        console.log("Next pressed!", e.getData());
        const bookACallIframe = this.getChildControl("book-a-call-iframe");
        this.setSelection([bookACallIframe]);
      });
    },
  }
});
