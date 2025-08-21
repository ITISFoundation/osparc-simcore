/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * The loading page
 *
 * -----------------------
 * |                  [] |
 * |                     |
 * | oSparc/service logo |
 * |   spinner + header  |
 * |     - msg_1         |
 * |     - msg_2         |
 * |     - msg_n         |
 * -----------------------
 *
 */
qx.Class.define("osparc.ui.message.Loading", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();
  },

  properties: {
    logo: {
      check: "String",
      init: null,
      nullable: true,
      apply: "__applyLogo"
    },

    header: {
      check: "String",
      nullable: true,
      apply: "__applyHeader"
    },

    messages: {
      check: "Array",
      nullable: true,
      apply: "__applyMessages"
    },

    /**
     * Show Restart-Maximize Toolbar
     */
    showToolbar: {
      check: "Boolean",
      init: false,
      event: "changeShowToolbar",
    }
  },

  events: {
    "restore" : "qx.event.type.Event",
    "maximize" : "qx.event.type.Event",
  },

  statics: {
    ICON_WIDTH: 190,
    LOGO_HEIGHT: 100,
    ICON_HEIGHT: 220,
    STATUS_ICON_SIZE: 20,
  },

  members: {
    __extraWidgets: null,
    __maxButton: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "max-toolbar":
          control = this.__createMaximizeToolbar();
          this._add(control);
          break;
        case "spacer-top":
          control = new qx.ui.core.Spacer();
          this._add(control, {
            flex: 1,
          });
          break;
        case "thumbnail":
          control = this.__createThumbnail();
          this._add(control);
          break;
        case "loading-title":
          control = new qx.ui.basic.Atom().set({
            icon: "@FontAwesome5Solid/circle-notch/"+this.self().STATUS_ICON_SIZE,
            font: "title-18",
            alignX: "center",
            rich: true,
            gap: 15,
            allowGrowX: false,
          });
          osparc.service.StatusUI.updateCircleAnimation(control.getChildControl("icon"));
          control.getChildControl("label").set({
            rich: true,
            wrap: true,
            alignX: "center",
          });
          this._add(control);
          break;
        case "messages-container":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
            alignX: "center"
          }));
          this._add(control);
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("max-toolbar");
      this.getChildControl("spacer-top");
      this.getChildControl("thumbnail");
      this.getChildControl("loading-title");
      this.getChildControl("messages-container");

      const extraWidgets = this.__extraWidgets = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      }));
      this._add(extraWidgets);

      const bottomSpacer = new qx.ui.core.Spacer();
      this._add(bottomSpacer, {
        flex: 1,
      });
    },

    maximizeIFrame: function(maximize) {
      if (maximize) {
        this.fireEvent("maximize");
        this.addState("maximized");
      } else {
        this.fireEvent("restore");
        this.removeState("maximized");
      }
      const maxButton = this.__maxButton;
      maxButton.set({
        label: osparc.widget.PersistentIframe.getZoomLabel(maximize),
        icon: osparc.widget.PersistentIframe.getZoomIcon(maximize)
      });
      osparc.utils.Utils.setIdToWidget(maxButton, osparc.widget.PersistentIframe.getMaximizeWidgetId(maximize));
      qx.event.message.Bus.getInstance().dispatchByName("maximizeIframe", this.hasState("maximized"));
    },

    __createMaximizeToolbar: function() {
      const maximize = false;
      const maxButton = this.__maxButton = osparc.widget.PersistentIframe.createToolbarButton(maximize).set({
        maxHeight: 25,
        label: osparc.widget.PersistentIframe.getZoomLabel(maximize),
        icon: osparc.widget.PersistentIframe.getZoomIcon(maximize),
      });
      osparc.utils.Utils.setIdToWidget(maxButton, osparc.widget.PersistentIframe.getMaximizeWidgetId(maximize));
      maxButton.addListener("execute", () => this.maximizeIFrame(!this.hasState("maximized")), this);

      const toolbarLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
        alignX: "right",
      }));
      this.bind("showToolbar", toolbarLayout, "visibility", {
        converter: showToolbar => showToolbar ? "visible" : "excluded"
      });
      toolbarLayout.add(maxButton);
      return toolbarLayout;
    },

    __createThumbnail: function() {
      const productLogoPath = osparc.product.Utils.getLogoPath();
      const thumbnail = new osparc.ui.basic.Thumbnail(productLogoPath, this.self().ICON_WIDTH, this.self().LOGO_HEIGHT).set({
        alignX: "center"
      });
      let logoHeight = this.self().LOGO_HEIGHT;
      if (qx.util.ResourceManager.getInstance().getImageFormat(productLogoPath) === "png") {
        logoHeight = osparc.ui.basic.Logo.getHeightKeepingAspectRatio(productLogoPath, this.self().ICON_WIDTH);
        thumbnail.getChildControl("image").set({
          width: this.self().ICON_WIDTH,
          height: logoHeight
        });
      } else {
        thumbnail.getChildControl("image").set({
          width: this.self().ICON_WIDTH,
          height: logoHeight
        });
      }
      return thumbnail;
    },

    __applyLogo: function(newLogo) {
      const productLogoPath = osparc.product.Utils.getLogoPath();
      const thumbnail = this.getChildControl("thumbnail");
      if (newLogo !== productLogoPath) {
        thumbnail.set({
          maxHeight: this.self().ICON_HEIGHT,
          height: this.self().ICON_HEIGHT,
        });
        thumbnail.getChildControl("image").set({
          maxHeight: this.self().ICON_HEIGHT,
          height: this.self().ICON_HEIGHT,
        });
      }
      thumbnail.setSource(newLogo);
    },

    __applyHeader: function(value) {
      const loadingTitle = this.getChildControl("loading-title");
      loadingTitle.setLabel(value);
      const words = value.split(" ");
      if (words.length) {
        const state = words[0];
        const iconSource = osparc.service.StatusUI.getIconSource(state.toLowerCase(), this.self().STATUS_ICON_SIZE);
        if (iconSource) {
          loadingTitle.setIcon(iconSource);
          osparc.service.StatusUI.updateCircleAnimation(loadingTitle.getChildControl("icon"));
        }
      }
    },

    __applyMessages: function(msgs) {
      this.clearMessages();

      const messagesContainer = this.getChildControl("messages-container");
      if (msgs) {
        msgs.forEach(msg => {
          const text = new qx.ui.basic.Label(msg.toString()).set({
            font: "text-18",
            rich: true,
            wrap: true
          });
          messagesContainer.add(text);
        });
        messagesContainer.show();
      } else {
        messagesContainer.exclude();
      }
    },

    clearMessages: function() {
      const messagesContainer = this.getChildControl("messages-container");
      messagesContainer.removeAll();
    },

    getMessageLabels: function() {
      return this.getChildControl("messages-container").getChildren();
    },

    addWidgetToMessages: function(widget) {
      const messagesContainer = this.getChildControl("messages-container");
      if (widget) {
        messagesContainer.add(widget);
        messagesContainer.show();
      } else {
        messagesContainer.exclude();
      }
    },

    addExtraWidget: function(widget) {
      this.__extraWidgets.add(widget);
    },
  }
});
