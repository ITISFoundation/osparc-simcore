/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Window that shows a text area with a given input text.
 * It can be used to dit a longer texts
 */

qx.Class.define("osparc.editor.MarkdownEditor", {
  extend: osparc.editor.TextEditor,

  /**
    * @param initText {String} Initialization text
    */
  construct: function(initText = "") {
    this.base(arguments, initText);

    this.getChildControl("preview-markdown");
    this.getChildControl("subtitle").set({
      value: this.tr("Markdown supported")
    });
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "preview-markdown": {
          control = new osparc.ui.markdown.Markdown().set({
            padding: 3,
          });
          const textArea = this.getChildControl("text-area");
          textArea.bind("value", control, "value");
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
