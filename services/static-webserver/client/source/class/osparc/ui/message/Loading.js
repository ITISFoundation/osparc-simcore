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

    GRID_POS: {
      TOOLBAR: 0,
      SPACER_TOP: 1,
      LOGO: 2,
      WAITING: 3,
      MESSAGES: 4,
      EXTRA_WIDGETS: 5,
      SPACER_BOTTOM: 6,
    }
  },

  members: {
    __thumbnail: null,
    __header: null,
    __messagesContainer: null,
    __extraWidgets: null,
    __maxButton: null,

    __buildLayout: function() {
      const maxLayout = this.__createMaximizeToolbar();
      this.bind("showToolbar", maxLayout, "visibility", {
        converter: showToolbar => showToolbar ? "visible" : "excluded"
      });
      this._addAt(maxLayout, this.self().GRID_POS.TOOLBAR);

      const topSpacer = new qx.ui.core.Spacer();
      this._addAt(topSpacer, this.self().GRID_POS.SPACER_TOP, {
        flex: 1,
      });

      const productLogoPath = osparc.product.Utils.getLogoPath();
      const thumbnail = this.__thumbnail = new osparc.ui.basic.Thumbnail(productLogoPath, this.self().ICON_WIDTH, this.self().LOGO_HEIGHT).set({
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
      this._addAt(thumbnail, this.self().GRID_POS.LOGO);

      const waitingHeader = this.__header = new qx.ui.basic.Atom().set({
        icon: "@FontAwesome5Solid/circle-notch/"+this.self().STATUS_ICON_SIZE,
        font: "title-18",
        alignX: "center",
        rich: true,
        gap: 15,
        allowGrowX: false,
      });
      const icon = waitingHeader.getChildControl("icon");
      osparc.service.StatusUI.updateCircleAnimation(icon);
      const label = waitingHeader.getChildControl("label");
      label.set({
        rich: true,
        wrap: true,
        alignX: "center",
      });
      this._addAt(waitingHeader, this.self().GRID_POS.WAITING);

      const messages = this.__messagesContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      }));
      this._addAt(messages, this.self().GRID_POS.MESSAGES);

      const extraWidgets = this.__extraWidgets = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      }));
      this._addAt(extraWidgets, this.self().GRID_POS.EXTRA_WIDGETS);

      const bottomSpacer = new qx.ui.core.Spacer();
      this._addAt(bottomSpacer, this.self().GRID_POS.SPACER_BOTTOM, {
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
      toolbarLayout.add(maxButton);
      return toolbarLayout;
    },

    __applyLogo: function(newLogo) {
      const productLogoPath = osparc.product.Utils.getLogoPath();
      if (newLogo !== productLogoPath) {
        this.__thumbnail.set({
          maxHeight: this.self().ICON_HEIGHT,
          height: this.self().ICON_HEIGHT,
        });
        this.__thumbnail.getChildControl("image").set({
          maxHeight: this.self().ICON_HEIGHT,
          height: this.self().ICON_HEIGHT,
        });
      }
      this.__thumbnail.setSource(newLogo);
    },

    __applyHeader: function(value) {
      this.__header.setLabel(value);
      const words = value.split(" ");
      if (words.length) {
        const state = words[0];
        const iconSource = osparc.service.StatusUI.getIconSource(state.toLowerCase(), this.self().STATUS_ICON_SIZE);
        if (iconSource) {
          this.__header.setIcon(iconSource);
          osparc.service.StatusUI.updateCircleAnimation(this.__header.getChildControl("icon"));
        }
      }
    },

    __applyMessages: function(msgs) {
      this.clearMessages();
      if (msgs) {
        msgs.forEach(msg => {
          const text = new qx.ui.basic.Label(msg.toString()).set({
            font: "text-18",
            rich: true,
            wrap: true
          });
          this.__messagesContainer.add(text);
        });
        this.__messagesContainer.show();
      } else {
        this.__messagesContainer.exclude();
      }
    },

    clearMessages: function() {
      this.__messagesContainer.removeAll();
    },

    getMessageLabels: function() {
      return this.__messagesContainer.getChildren();
    },

    addWidgetToMessages: function(widget) {
      if (widget) {
        this.__messagesContainer.add(widget);
        this.__messagesContainer.show();
      } else {
        this.__messagesContainer.exclude();
      }
    },

    addExtraWidget: function(widget) {
      this.__extraWidgets.add(widget);
    },
  }
});
