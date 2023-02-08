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
   * @param {Boolean} showMaximize
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
      nullable: true,
      apply: "__applyDisclaimer"
    },

    logo: {
      check: "String",
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
    }
  },

  // from osparc.component.widget.PersistentIframe
  events: {
    /** Fired if the iframe is restored from a minimized or maximized state */
    "restore" : "qx.event.type.Event",
    /** Fired if the iframe is maximized */
    "maximize" : "qx.event.type.Event"
  },

  statics: {
    LOGO_WIDTH: 208,
    LOGO_HEIGHT: 88,
    STATUS_ICON_SIZE: 32
  },

  members: {
    __maxButton: null,
    __mainLayout: null,
    __disclaimer: null,
    __logo: null,
    __header: null,
    __messages: null,
    __extraWidgets: null,

    __buildLayout: function(showMaximize) {
      const mainLayout = this.__mainLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(20).set({
        alignX: "center",
        alignY: "middle"
      })).set({
        maxWidth: this.self().LOGO_WIDTH*2,
        padding: 20
      });
      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });
      this._add(mainLayout);
      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });

      const disclaimer = this.__disclaimer = new qx.ui.basic.Atom().set({
        icon: "@FontAwesome5Solid/exclamation-triangle/20",
        alignX: "center"
      });

      const image = this.__logo = new osparc.ui.basic.Logo().set({
        width: this.self().LOGO_WIDTH,
        height: this.self().LOGO_HEIGHT
      });

      const atom = this.__header = new qx.ui.basic.Atom().set({
        icon: "@FontAwesome5Solid/circle-notch/"+this.self().STATUS_ICON_SIZE,
        font: "nav-bar-label",
        alignX: "center",
        gap: 15,
        allowGrowX: false
      });
      const label = atom.getChildControl("label");
      label.set({
        rich: true,
        wrap: true
      });
      const icon = atom.getChildControl("icon");
      osparc.utils.StatusUI.updateCircleAnimation(icon);

      const messages = this.__messages = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      }));

      const extraWidgets = this.__extraWidgets = new qx.ui.container.Composite(new qx.ui.layout.VBox(10).set({
        alignX: "center"
      }));
      mainLayout.add(disclaimer);
      mainLayout.add(image);
      mainLayout.add(atom);
      mainLayout.add(messages);
      mainLayout.add(extraWidgets);

      const maximize = false;
      const maxButton = this.__maxButton = new qx.ui.form.Button(null).set({
        icon: osparc.component.widget.PersistentIframe.getZoomIcon(maximize),
        visibility: showMaximize ? "visible" : "excluded",
        decorator: null
      });
      osparc.utils.Utils.setIdToWidget(maxButton, osparc.component.widget.PersistentIframe.getMaximizeWidgetId(maximize));
      maxButton.addListener("execute", () => this.maximizeIFrame(!this.hasState("maximized")), this);

      const maximizeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
        maxWidth: 40
      });
      maximizeLayout.add(maxButton);
      maximizeLayout.add(new qx.ui.core.Widget(), {
        flex: 1
      });
      this._add(maximizeLayout);
    },

    __applyLogo: function(value) {
      this.__mainLayout.remove(this.__logo);

      this.__logo = new osparc.ui.basic.Thumbnail(null, this.self().LOGO_WIDTH, this.self().LOGO_HEIGHT);
      const image = this.__logo.getChildControl("image");
      image.set({
        source: value
      });
      this.__mainLayout.addAt(this.__logo, 0);
    },

    __applyHeader: function(value) {
      this.__header.setLabel(value);
      const words = value.split(" ");
      if (words.length) {
        const state = words[0];
        const iconSource = osparc.utils.StatusUI.getIconSource(state.toLowerCase(), this.self().STATUS_ICON_SIZE);
        if (iconSource) {
          this.__header.setIcon(iconSource);
          osparc.utils.StatusUI.updateCircleAnimation(this.__header.getChildControl("icon"));
        }
      }
    },

    __applyMessages: function(msgs, old) {
      this.__messages.removeAll();
      msgs.forEach(msg => {
        const text = new qx.ui.basic.Label(msg.toString()).set({
          font: "text-18",
          rich: true,
          wrap: true
        });
        this.__messages.add(text);
      });
    },

    __applyDisclaimer: function(disclaimerText) {
      if (this.__disclaimer) {
        this._remove(this.__disclaimer);
        this.__disclaimer.removeAll();
      }
      const disclaimer = this.__disclaimer = new qx.ui.basic.Label(disclaimerText).set({
        font: "text-16",
        rich: true,
        wrap: true
      });
      this._add(disclaimer);
    },

    addWidgetToMessages: function(widget) {
      this.__messages.add(widget);
    },

    addExtraWidget: function(widget) {
      this.__extraWidgets.add(widget);
    },

    // from osparc.component.widget.PersistentIframe
    maximizeIFrame: function(maximize) {
      if (maximize) {
        this.fireEvent("maximize");
        this.addState("maximized");
      } else {
        this.fireEvent("restore");
        this.removeState("maximized");
      }
      const maxButton = this.__maxButton;
      maxButton.setIcon(osparc.component.widget.PersistentIframe.getZoomIcon(maximize));
      osparc.utils.Utils.setIdToWidget(maxButton, osparc.component.widget.PersistentIframe.getMaximizeWidgetId(maximize));
      qx.event.message.Bus.getInstance().dispatchByName("maximizeIframe", this.hasState("maximized"));
    }
  }
});
