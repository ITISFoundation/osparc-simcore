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

  construct: function(url, suggestions = []) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(8));

    this._createChildControlImpl("url-field");
    this.__thumbnails = this.getChildControl("scroll-thumbnails");

    this._createChildControlImpl("cancel-btn");
    this._createChildControlImpl("save-btn");

    if (url) {
      this.setUrl(url);
    }
    if (suggestions) {
      this.setSuggestions(suggestions);
    }
  },

  properties: {
    url: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeUrl"
    },

    suggestions: {
      check: "Array",
      init: [],
      nullable: true,
      event: "changeSuggestions",
      apply: "__applySuggestions"
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
    __thumbnails: null,

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
        case "scroll-thumbnails":
          control = new qx.ui.container.SlideBar().set({
            alignX: "center",
            maxHeight: 170
          });
          [
            control.getChildControl("button-backward"),
            control.getChildControl("button-forward")
          ].forEach(btn => {
            btn.set({
              maxWidth: 30,
              maxHeight: 30,
              alignY: "middle",
              marginLeft: 5,
              marginRight: 5,
              icon: "@FontAwesome5Solid/ellipsis-h/16",
              backgroundColor: "transparent"
            });
          });
          control.setLayout(new qx.ui.layout.HBox(5).set({
            alignX: "center"
          }));
          this._add(control, {
            flex: 1
          });
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
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
          control = new qx.ui.form.Button(this.tr("Save"));
          control.addListener("execute", () => {
            const urlField = this.getChildControl("url-field");
            const validUrl = this.self().sanitizeUrl(urlField.getValue());
            if (validUrl) {
              this.fireDataEvent("updateThumbnail", validUrl);
            }
          }, this);
          buttons.add(control);
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __applySuggestions: function(suggestions) {
      this.__thumbnails.removeAll();
      suggestions.forEach(suggestion => {
        const thumbnail = new osparc.ui.basic.Thumbnail(suggestion, 170, 124);
        thumbnail.addListener("tap", () => {
          this.setUrl(thumbnail.getChildControl("image").getSource());
        });
        this.__thumbnails.add(thumbnail);
      });
    }
  }
});
