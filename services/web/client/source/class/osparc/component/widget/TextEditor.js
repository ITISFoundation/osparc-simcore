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
  extend: osparc.ui.window.Window,

  construct: function(oldText = "", subtitle = "", winTitle) {
    this.base(arguments, winTitle || this.tr("Edit text"));

    this.set({
      appearance: "window-small-cap",
      layout: new qx.ui.layout.VBox(2),
      autoDestroy: true,
      padding: 2,
      modal: true,
      showMaximize: false,
      showMinimize: false,
      width: 400,
      height: 300,
      clickAwayClose: true
    });

    this.__populateTextArea(oldText);
    this.__addSubtitle(subtitle);
    this.__addButtons();
    this.__attachEventHandlers();
  },

  events: {
    "textChanged": "qx.event.type.Data"
  },

  members: {
    __textArea: null,

    __populateTextArea: function(oldLabel) {
      // Create a text area in which to edit the data
      const textArea = this.__textArea = new qx.ui.form.TextArea(oldLabel).set({
        allowGrowX: true
      });

      this.addListener("appear", () => {
        if (textArea.getValue()) {
          textArea.setTextSelection(0, textArea.getValue().length);
        }
      }, this);

      this.add(textArea, {
        flex: 1
      });
    },

    __addSubtitle: function(subtitleLabel) {
      if (subtitleLabel) {
        const subtitle = new qx.ui.basic.Label(subtitleLabel).set({
          font: "text-12"
        });
        this.add(subtitle);
      }
    },

    __addButtons: function() {
      const buttonsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "right"
      }));

      const cancel = new qx.ui.form.Button(this.tr("Cancel"));
      cancel.addListener("execute", e => {
        this.close();
      }, this);
      buttonsLayout.add(cancel);

      const save = new qx.ui.form.Button(this.tr("Accept"));
      save.addListener("execute", e => {
        const newText = this.__textArea.getValue();
        this.fireDataEvent("textChanged", newText);
      }, this);
      buttonsLayout.add(save);

      this.add(buttonsLayout);
    },

    __attachEventHandlers: function() {
      let commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        this.close();
        commandEsc.dispose();
        commandEsc = null;
      });
    }
  }
});
