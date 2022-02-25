/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.editor.ThumbnailEditor", {
  extend: qx.ui.core.Widget,

  construct: function(url) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    if (url) {
      this.set({
        url
      });
    }

    this._createChildControlImpl("url-field");
    this._createChildControlImpl("cancel-btn");
    this._createChildControlImpl("save-btn");
  },

  properties: {
    url: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeUrl"
    }
  },

  events: {
    "updateThumbnail": "qx.event.type.Data",
    "cancel": "qx.event.type.Event"
  },

  statics: {
    sanitizeUrl: function(dirty) {
      const clean = osparc.wrapper.DOMPurify.getInstance().sanitize(dirty);
      if ((dirty && dirty !== clean) || (clean !== "" && !osparc.utils.Utils.isValidHttpUrl(clean))) {
        osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Error checking link"), "WARNING");
        return null;
      }
      return clean;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "url-field":
          control = new qx.ui.form.TextField().set({
            font: "text-14",
            backgroundColor: "background-main",
            placeholder: this.tr("url")
          });
          this.bind("url", control, "value");
          this._add(control);
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(8).set({
            alignX: "right"
          }));
          this._add(control);
          break;
        case "cancel-btn": {
          const buttons = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button(this.tr("Cancel"));
          control.addListener("execute", () => this.fireEvent("cancel"), this);
          buttons.add(control);
          break;
        }
        case "save-btn": {
          const buttons = this.getChildControl("buttons-layout");
          control = new osparc.ui.form.FetchButton(this.tr("Save"));
          control.addListener("execute", () => {
            control.setFecthing(control);
            const urlField = this.getChildControl("url-field");
            const validUrl = this.sanitizeUrl(urlField.getValue());
            if (validUrl) {
              this.firedataEvent("updateThumbnail", validUrl);
            }
          }, this);
          buttons.add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    }
  }
});
