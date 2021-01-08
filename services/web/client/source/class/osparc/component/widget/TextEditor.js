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

    this.__populateTextArea(initText);
    this.__addSubtitle(subtitleText);
    this.__addButtons();
  },

  events: {
    "textChanged": "qx.event.type.Data",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __textArea: null,

    __populateTextArea: function(initText) {
      // Create a text area in which to edit the data
      const textArea = this.__textArea = new qx.ui.form.TextArea(initText).set({
        allowGrowX: true
      });

      this.addListener("appear", () => {
        if (textArea.getValue()) {
          textArea.setTextSelection(0, textArea.getValue().length);
        }
      }, this);

      this._add(textArea, {
        flex: 1
      });
    },

    __addSubtitle: function(subtitleText) {
      if (subtitleText) {
        const subtitle = new qx.ui.basic.Label(subtitleText).set({
          font: "text-12"
        });
        this._add(subtitle);
      }
    },

    __addButtons: function() {
      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "right"
      }));

      const cancel = new qx.ui.form.Button(this.tr("Cancel"));
      cancel.addListener("execute", () => {
        this.fireDataEvent("cancel");
      }, this);
      buttonsLayout.add(cancel);

      const save = new qx.ui.form.Button(this.tr("Accept"));
      save.addListener("execute", () => {
        const newText = this.__textArea.getValue();
        this.fireDataEvent("textChanged", newText);
      }, this);
      buttonsLayout.add(save);

      this._add(buttonsLayout);
    }
  }
});
