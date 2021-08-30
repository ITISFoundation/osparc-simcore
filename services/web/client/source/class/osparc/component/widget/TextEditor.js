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

qx.Class.define("osparc.component.widget.TextEditor", {
  extend: qx.ui.core.Widget,

  /**
    * @param initText {String} Initialization text
    * @param subtitleText {String} Text to be shown under the text area
    */
  construct: function(initText = "", subtitleText = "") {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(2));

    this._populateTextArea(initText);
    this.__addSubtitle(subtitleText);
    this.__addButtons();
  },

  events: {
    "textChanged": "qx.event.type.Data",
    "cancel": "qx.event.type.Event"
  },

  members: {
    _textArea: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "text-area":
          control = new qx.ui.form.TextArea().set({
            allowGrowX: true
          });
          this._add(control, {
            flex: 1
          });
          break;
        case "subtitle":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this._add(control);
          break;
        case "buttons":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
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
            const newText = this._textArea.getValue();
            this.fireDataEvent("textChanged", newText);
          }, this);
          buttons.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _populateTextArea: function(initText) {
      const textArea = this._textArea = this.getChildControl("text-area").set({
        value: initText
      });
      this.addListener("appear", () => {
        if (textArea.getValue()) {
          textArea.setTextSelection(0, textArea.getValue().length);
        }
        osparc.wrapper.CodeMirror.getInstance().convertTextArea(textArea);
      }, this);
    },

    __addSubtitle: function(subtitleText) {
      if (subtitleText) {
        this.getChildControl("subtitle").set({
          value: subtitleText
        });
      }
    },

    __addButtons: function() {
      this.getChildControl("cancel-button");
      this.getChildControl("accept-button");
    }
  }
});
