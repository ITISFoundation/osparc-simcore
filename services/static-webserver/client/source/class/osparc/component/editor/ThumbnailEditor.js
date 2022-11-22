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

    this.getChildControl("url-field");
    this.getChildControl("scroll-thumbnails");
    const suggestionsLayout = this.getChildControl("thumbnails-layout");
    suggestionsLayout.exclude();

    this.getChildControl("cancel-btn");
    this.getChildControl("save-btn");

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
        case "thumbnails-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          const label = new qx.ui.basic.Label(this.tr("or pick one from the list of services:"));
          control.add(label);
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "scroll-thumbnails": {
          const thumbnailsLayout = this.getChildControl("thumbnails-layout");
          control = new osparc.component.widget.SlideBar().set({
            alignX: "center",
            maxHeight: 170
          });
          control.setButtonsWidth(30);
          thumbnailsLayout.add(control);
          control.setLayout(new qx.ui.layout.HBox(5).set({
            alignX: "center"
          }));
          break;
        }
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
      const thumbnailsLayout = this.getChildControl("scroll-thumbnails");
      thumbnailsLayout.removeAll();
      suggestions.forEach(suggestion => {
        const thumbnail = new osparc.ui.basic.Thumbnail(suggestion, 170, 124);
        thumbnail.addListener("tap", () => {
          this.setUrl(thumbnail.getChildControl("image").getSource());
          thumbnailsLayout.getChildren().forEach(thumbnailImg => osparc.utils.Utils.removeBorder(thumbnailImg));
          osparc.utils.Utils.addBorder(thumbnail, 1, "#007fd4"); // Visual Studio blue
        });
        thumbnailsLayout.add(thumbnail);
      });
      this.getChildControl("thumbnails-layout").setVisibility(suggestions.length ? "visible" : "excluded");
    }
  }
});
