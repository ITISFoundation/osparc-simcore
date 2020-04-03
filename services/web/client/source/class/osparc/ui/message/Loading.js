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
 * --------------------
 * |   oSparc logo    |
 * | spinner + header |
 * |  - msg_1         |
 * |  - msg_2         |
 * |  - msg_n         |
 * --------------------
 *
 */
qx.Class.define("osparc.ui.message.Loading", {
  extend: qx.ui.core.Widget,

  /**
   * Constructor for the Loading widget.
   *
   * @param {String} header Header that goes next to the spinning wheel.
   * @param {Array} messages Texts that will displayed as bullet points under the header.
   */
  construct: function(header = "", messages = [], showMaximize = false) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());

    this.__buildLayout(showMaximize);

    this.setHeader(header);
    this.setMessages(messages);
  },

  properties: {
    header: {
      check: "String",
      nullable: true,
      apply: "_applyHeader"
    },

    messages: {
      check: "Array",
      nullable: true,
      apply: "_applyMessages"
    }
  },

  // from osparc.component.widget.PersistentIframe
  events: {
    /** Fired if the iframe is restored from a minimized or maximized state */
    "restore" : "qx.event.type.Event",
    /** Fired if the iframe is maximized */
    "maximize" : "qx.event.type.Event"
  },

  members: {
    __header: null,
    __messages: null,

    __maxButton: null,

    __buildLayout: function(showMaximize) {
      const image = new osparc.ui.basic.OSparcLogo().set({
        width: 200,
        height: 120
      });

      const atom = this.__header = new qx.ui.basic.Atom().set({
        icon: "@FontAwesome5Solid/circle-notch/32",
        font: "nav-bar-label",
        alignX: "center",
        gap: 15
      });
      atom.getChildControl("icon").getContentElement().addClass("rotate");

      const messages = this.__messages = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        padding: 20
      });

      const loadingWidget = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignY: "middle"
      }));
      loadingWidget.add(new qx.ui.core.Widget(), {
        flex: 1
      });
      loadingWidget.add(image);
      loadingWidget.add(atom);
      loadingWidget.add(messages);
      loadingWidget.add(new qx.ui.core.Widget(), {
        flex: 1
      });

      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });
      this._add(loadingWidget);
      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });
      if (showMaximize) {
        const maximize = false;
        const maxButton = this.__maxButton = new qx.ui.form.Button(null).set({
          icon: osparc.component.widget.PersistentIframe.getIcon(maximize),
          decorator: null
        });
        osparc.utils.Utils.setIdToWidget(maxButton, osparc.component.widget.PersistentIframe.getMaximizeWidgetId(maximize));
        maxButton.addListener("execute", e => {
          this.maximizeIFrame(!this.hasState("maximized"));
        }, this);

        const maximizeLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
          maxWidth: 40
        });
        maximizeLayout.add(maxButton);
        maximizeLayout.add(new qx.ui.core.Widget(), {
          flex: 1
        });
        this._add(maximizeLayout);
      }
    },

    _applyHeader: function(value, old) {
      this.__header.setLabel(value);
    },

    _applyMessages: function(msgs, old) {
      this.__messages.removeAll();
      msgs.forEach(msg => {
        const text = new qx.ui.basic.Label("- " + msg.toString()).set({
          font: "text-18"
        });
        this.__messages.add(text);
      });
    },



    // from osparc.component.widget.PersistentIframe
    maximizeIFrame: function(maximize) {
      const maxButton = this.__maxButton;
      if (maximize) {
        this.fireEvent("maximize");
        this.addState("maximized");
      } else {
        this.fireEvent("restore");
        this.removeState("maximized");
      }
      maxButton.setIcon(osparc.component.widget.PersistentIframe.getIcon(maximize));
      osparc.utils.Utils.setIdToWidget(maxButton, osparc.component.widget.PersistentIframe.getMaximizeWidgetId(maximize));
      qx.event.message.Bus.getInstance().dispatchByName("maximizeIframe", this.hasState("maximized"));
    }
  }
});
