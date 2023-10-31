/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.editor.HtmlEditor", {
  extend: osparc.editor.TextEditor,

  /**
    * @param initText {String} Initialization text
    */
  construct: function(initText = "") {
    this.base(arguments, initText);

    this.getChildControl("preview-html");
    this.getChildControl("subtitle").set({
      value: this.tr("Supports HTML")
    });
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "preview-html": {
          control = new qx.ui.embed.Html();
          const textArea = this.getChildControl("text-area");
          textArea.bind("value", control, "html");
          const tabs = this.getChildControl("tabs");
          const previewPage = new qx.ui.tabview.Page(this.tr("Preview")).set({
            layout: new qx.ui.layout.VBox(5)
          });
          previewPage.getChildControl("button").getChildControl("label").set({
            font: "text-13"
          });
          const scrollContainer = new qx.ui.container.Scroll();
          scrollContainer.add(control);
          previewPage.add(scrollContainer, {
            flex: 1
          });
          tabs.add(previewPage);
          break;
        }
      }
      return control || this.base(arguments, id);
    }
  }
});
