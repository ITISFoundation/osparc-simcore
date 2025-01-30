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
    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      alignX: "center",
      alignY: "middle",
    });

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

    toolbarHeight: {
      check: "Integer",
      init: 25
    },

    /**
     * Show Restart-Maximize Toolbar
     */
    showToolbar: {
      check: "Boolean",
      init: true,
      event: "changeShowToolbar",
    },
  },

  // from osparc.widget.PersistentIframe
  events: {
    /** Fired if the iframe is restored from a minimized or maximized state */
    "restore" : "qx.event.type.Event",
    /** Fired if the iframe is maximized */
    "maximize" : "qx.event.type.Event"
  },

  statics: {
    ICON_WIDTH: 190,
    LOGO_HEIGHT: 100,
    ICON_HEIGHT: 220,
    STATUS_ICON_SIZE: 20,

    GRID_POS: {
      LOGO: 1,
      WAITING: 2,
      MESSAGES: 3,
      EXTRA_WIDGETS: 4
    }
  },

  members: {
    __thumbnail: null,
    __header: null,
    __messagesContainer: null,
    __extraWidgets: null,
    __maxButton: null,

    __buildLayout: function() {
      this.__createMaximizeButton();
      this.__createMainLayout();
    },

    __createMaximizeButton: function() {
      const maximize = false;
      const maxButton = this.__maxButton = osparc.widget.PersistentIframe.createToolbarButton(maximize).set({
        label: osparc.widget.PersistentIframe.getZoomLabel(maximize),
        icon: osparc.widget.PersistentIframe.getZoomIcon(maximize),
      });
      osparc.utils.Utils.setIdToWidget(maxButton, osparc.widget.PersistentIframe.getMaximizeWidgetId(maximize));
      maxButton.addListener("execute", () => this.maximizeIFrame(!this.hasState("maximized")), this);

      const buttonsContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "right",
        alignY: "middle"
      }));
      this.bind("showToolbar", buttonsContainer, "visibility", {
        converter: showToolbar => showToolbar ? "visible" : "excluded"
      });
      buttonsContainer.add(maxButton);
      this._add(buttonsContainer);
    },

    __createMainLayout: function() {
      const layout = new qx.ui.layout.Grid(20, 20);
      layout.setColumnFlex(0, 1);
      layout.setColumnAlign(0, "center", "middle");
      const mainLayout = new qx.ui.container.Composite(layout).set({
        maxWidth: 400,
        alignX: "center",
      });
      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this._add(mainLayout);
      this._add(new qx.ui.core.Spacer(), {
        flex: 1
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
      mainLayout.add(thumbnail, {
        column: 0,
        row: this.self().GRID_POS.LOGO
      });

      const waitingHeader = this.__header = new qx.ui.basic.Atom().set({
        icon: "@FontAwesome5Solid/circle-notch/"+this.self().STATUS_ICON_SIZE,
        font: "title-18",
        alignX: "center",
        rich: true,
        gap: 15,
        allowGrowX: false
      });
      const label = waitingHeader.getChildControl("label");
      label.set({
        rich: true,
        wrap: true
      });
      const icon = waitingHeader.getChildControl("icon");
      osparc.service.StatusUI.updateCircleAnimation(icon);
      mainLayout.add(waitingHeader, {
        column: 0,
        row: this.self().GRID_POS.WAITING
      });

      const messages = this.__messagesContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      }));
      mainLayout.add(messages, {
        column: 0,
        row: this.self().GRID_POS.MESSAGES
      });

      const extraWidgets = this.__extraWidgets = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      }));
      mainLayout.add(extraWidgets, {
        column: 0,
        row: this.self().GRID_POS.EXTRA_WIDGETS
      });
    },

    __applyShowToolbar: function(show) {
      this.setToolbarHeight(show ? 25 : 0);
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

    // from osparc.widget.PersistentIframe
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
    }
  }
});
