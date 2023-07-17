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

qx.Class.define("osparc.component.editor.TextEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param initText {String} Initialization text
    */
  construct: function(initText = "") {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(2));

    this.__textArea = this.getChildControl("text-area");
    this.getChildControl("preview");
    if (initText) {
      this.setText(initText);
    }

    this.__addButtons();
  },

  events: {
    "textChanged": "qx.event.type.Data",
    "cancel": "qx.event.type.Event"
  },

  properties: {
    text: {
      check: "String",
      event: "changeText",
      init: "",
      nullable: true
    }
  },

  members: {
    __textArea: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "tabs":
          control = new qx.ui.tabview.TabView().set({
            contentPadding: 0,
            barPosition: "top"
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "text-area": {
          control = new qx.ui.form.TextArea().set({
            allowGrowX: true
          });
          control.addListener("appear", () => {
            if (control.getValue()) {
              control.setTextSelection(0, control.getValue().length);
            }
          }, this);
          this.bind("text", control, "value");
          const tabs = this.getChildControl("tabs");
          const writePage = new qx.ui.tabview.Page(this.tr("Write")).set({
            layout: new qx.ui.layout.VBox(5)
          });
          writePage.getChildControl("button").getChildControl("label").set({
            font: "text-13"
          });
          writePage.add(control, {
            flex: 1
          });
          const subtitle = this.getChildControl("subtitle").set({
            value: this.tr("Supports Markdown")
          });
          writePage.add(subtitle);
          tabs.add(writePage);
          break;
        }
        case "preview": {
          control = new osparc.ui.markdown.Markdown().set({
            padding: 3,
            noMargin: true
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
        case "subtitle":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this._add(control);
          break;
        case "buttons":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: "right"
          }));
          this._add(control);
          break;
        case "cancel-button": {
          const buttons = this.getChildControl("buttons");
          control = new qx.ui.form.Button(this.tr("Cancel"));
          control.addListener("execute", () => {
            this.fireDataEvent("cancel");
          }, this);
          buttons.add(control);
          break;
        }
        case "accept-button": {
          const buttons = this.getChildControl("buttons");
          control = new qx.ui.form.Button(this.tr("Save"));
          control.addListener("execute", () => {
            const newText = this.__textArea.getValue();
            this.fireDataEvent("textChanged", newText);
          }, this);
          buttons.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __addButtons: function() {
      this.getChildControl("cancel-button");
      this.getChildControl("accept-button");
    }
  }
});
