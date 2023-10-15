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
 * |     disclaimer      |
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

  /**
   * Constructor for the Loading widget.
   *
   * @param {Boolean} showMaximizeButton
   */
  construct: function(showMaximizeButton = false) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());

    this.set({
      alignX: "center"
    });
    this.__buildLayout(showMaximizeButton);
  },

  properties: {
    disclaimer: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeDisclaimer"
    },

    logo: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeLogo"
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
    }
  },

  // from osparc.widget.PersistentIframe
  events: {
    /** Fired if the iframe is restored from a minimized or maximized state */
    "restore" : "qx.event.type.Event",
    /** Fired if the iframe is maximized */
    "maximize" : "qx.event.type.Event"
  },

  statics: {
    LOGO_WIDTH: 240,
    LOGO_HEIGHT: 100,
    STATUS_ICON_SIZE: 32,

    GRID_POS: {
      DISCLAIMER: 0,
      LOGO: 1,
      WAITING: 2,
      MESSAGES: 3,
      EXTRA_WIDGETS: 4
    }
  },

  members: {
    __mainLayout: null,
    __header: null,
    __messages: null,
    __extraWidgets: null,
    __maxButton: null,

    __buildLayout: function(showMaximizeButton) {
      this.__createMainLayout();
      this.__createMaximizeButton(showMaximizeButton);
    },

    __createMainLayout: function() {
      const layout = new qx.ui.layout.Grid(20, 20);
      layout.setColumnFlex(0, 1);
      const mainLayout = this.__mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      })).set({
        width: this.self().LOGO_WIDTH*3,
        maxWidth: this.self().LOGO_WIDTH*3,
        padding: 20
      });
      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });
      this._add(mainLayout);
      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });

      const disclaimer = new qx.ui.basic.Atom().set({
        padding: 15,
        gap: 20,
        icon: "@FontAwesome5Solid/exclamation-triangle/20",
        backgroundColor: "warning-yellow-s4l",
        textColor: "black",
        alignX: "center"
      });
      osparc.utils.Utils.setIdToWidget(disclaimer, "disclaimerMessage");
      disclaimer.getContentElement().setStyles({
        "border-radius": "8px"
      });
      disclaimer.getChildControl("label").set({
        font: "text-16",
        textColor: "black",
        rich: true,
        wrap: true
      });
      this.bind("disclaimer", disclaimer, "visibility", {
        converter: d => d ? "visible" : "excluded"
      });
      this.bind("disclaimer", disclaimer, "label");
      mainLayout.addAt(disclaimer, {
        column: 0,
        row: this.self().GRID_POS.DISCLAIMER
      });

      const defaultLogoPath = osparc.product.Utils.getLogoPath();
      const logo = new osparc.ui.basic.Thumbnail(defaultLogoPath, this.self().LOGO_WIDTH, this.self().LOGO_HEIGHT).set({
        alignX: "center"
      });
      /*
      // this is needed for svg images, but it breaks the GUI if the image source changes
      logo.getChildControl("image").set({
        minWidth: parseInt(this.self().LOGO_WIDTH/1.5),
        minHeight: parseInt(this.self().LOGO_HEIGHT/1.5)
      });
      */
      this.bind("logo", logo, "source", {
        converter: newPath => newPath ? newPath : defaultLogoPath
      });
      mainLayout.addAt(logo, {
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
      mainLayout.addAt(waitingHeader, {
        column: 0,
        row: this.self().GRID_POS.WAITING
      });

      const messages = this.__messages = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      }));
      mainLayout.addAt(messages, {
        column: 0,
        row: this.self().GRID_POS.MESSAGES
      });

      const extraWidgets = this.__extraWidgets = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      }));
      mainLayout.addAt(extraWidgets, {
        column: 0,
        row: this.self().GRID_POS.EXTRA_WIDGETS
      });
    },

    __createMaximizeButton: function(showMaximizeButton) {
      const maximize = false;
      const maxButton = this.__maxButton = osparc.widget.PersistentIframe.createToolbarButton(maximize).set({
        label: osparc.widget.PersistentIframe.getZoomLabel(maximize),
        icon: osparc.widget.PersistentIframe.getZoomIcon(maximize),
        visibility: showMaximizeButton ? "visible" : "excluded"
      });
      osparc.utils.Utils.setIdToWidget(maxButton, osparc.widget.PersistentIframe.getMaximizeWidgetId(maximize));
      maxButton.addListener("execute", () => this.maximizeIFrame(!this.hasState("maximized")), this);

      const maximizeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
        maxWidth: 100
      });
      maximizeLayout.add(maxButton);
      maximizeLayout.add(new qx.ui.core.Widget(), {
        flex: 1
      });
      this._add(maximizeLayout);
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

    __applyMessages: function(msgs, old) {
      this.__messages.removeAll();
      if (msgs) {
        msgs.forEach(msg => {
          const text = new qx.ui.basic.Label(msg.toString()).set({
            font: "text-18",
            rich: true,
            wrap: true
          });
          this.__messages.add(text);
        });
        this.__messages.show();
      } else {
        this.__messages.exclude();
      }
    },

    addWidgetToMessages: function(widget) {
      if (widget) {
        this.__messages.add(widget);
        this.__messages.show();
      } else {
        this.__messages.exclude();
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
