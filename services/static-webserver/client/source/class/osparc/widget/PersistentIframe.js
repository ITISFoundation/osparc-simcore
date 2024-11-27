/* ************************************************************************
   Copyright: 2018 ITIS Foundation
   License:   MIT
   Authors:   Tobi Oetiker <tobi@oetiker.ch>
   Utf8Check: äöü
************************************************************************ */

/**
 * When moving an iframe node in the dom, it reloads its content. This is
 * rather unfortunate when the content is another web application.
 * This Iframe widget solves the problem by attaching the iframe to a
 * permanent location and just moving it into position as the actual
 * widget manifests in different locations. There are limits as to where
 * the widget can be displayed as the widget hierarchy may prevent correct
 * visualisation. By default the iframe is attached to the root node of
 * the document, but an alternate attachment can be specified as required.
 *
 */

qx.Class.define("osparc.widget.PersistentIframe", {
  extend: qx.ui.embed.AbstractIframe,
  /**
   *
   * @param source {String} URL for the iframe content
   * @param poolEl {Element?} Dom node for attaching the iframe
   */
  construct: function(source, el) {
    this.base(arguments, source);

    this.themeSwitchHandler = msg => {
      this.postThemeSwitch(msg.getData());
    };

    this.postThemeSwitch = theme => {
      const iframe = this._getIframeElement();
      if (this._getIframeElement()) {
        const iframeDomEl = iframe.getDomElement();
        const iframeSource = iframe.getSource();
        if (iframeDomEl && iframeSource) {
          const msg = "osparc;theme=" + theme;
          try {
            iframeDomEl.contentWindow.postMessage(msg, iframeSource);
          } catch (err) {
            console.log(`Failed posting message ${msg} to iframe ${iframeSource}\n${err.message}`);
          }
        }
      }
    };

    qx.event.message.Bus.getInstance().subscribe("themeSwitch", this.themeSwitchHandler);
  },

  statics: {
    getZoomLabel: function(maximize) {
      return maximize ? "Restore" : "Maximize";
    },

    getZoomIcon: function(maximize) {
      const iconURL = maximize ? "window-restore" : "window-maximize";
      return osparc.theme.common.Image.URLS[iconURL] + "/20";
    },

    getMaximizeWidgetId: function(maximize) {
      return maximize ? "restoreBtn" : "maximizeBtn";
    },

    createToolbarButton: function() {
      return new qx.ui.form.Button().set({
        appearance: "fab-button",
        zIndex: 20,
        padding: [0, 5],
        marginRight: 10
      });
    },

    HIDDEN_TOP: -10000
  },

  properties: {
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
      apply: "__applyShowToolbar"
    }
  },

  events: {
    /** Fired for requesting a restart */
    "restart" : "qx.event.type.Event",
    /** Fired if the iframe is restored from a minimized or maximized state */
    "restore" : "qx.event.type.Event",
    /** Fired if the iframe is maximized */
    "maximize" : "qx.event.type.Event"
  },

  members: {
    __iframe: null,
    __syncScheduled: null,
    __buttonContainer: null,
    __diskUsageIndicator: null,
    __reloadButton: null,
    __zoomButton: null,

    // override
    _createContentElement : function() {
      let iframe = this.__iframe = new qx.ui.embed.Iframe(this.getSource());
      const persistentIframe = this;
      iframe.addListener("load", () => {
        const currentTheme = qx.theme.manager.Meta.getInstance().getTheme();
        if (currentTheme && persistentIframe.postThemeSwitch) {
          persistentIframe.postThemeSwitch(currentTheme.name);
        }
        this.fireEvent("load");
      });
      iframe.addListener("navigate", e => this.fireDataEvent("navigate", e.getData()));

      let standin = new qx.html.Element("div");
      let appRoot = this.getApplicationRoot();
      appRoot.add(iframe, {
        top: this.self().HIDDEN_TOP
      });
      const iframeEl = this._getIframeElement();
      const host = window.location.host;
      iframeEl.setAttribute("allow", `clipboard-read; clipboard-write; from *.services.${host}`);

      const buttonContainer = this.__buttonContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "right",
        alignY: "middle"
      }));

      const diskUsageIndicator = this.__diskUsageIndicator = new osparc.workbench.DiskUsageIndicator();
      diskUsageIndicator.getChildControl("disk-indicator").set({
        margin: 0
      });
      buttonContainer.add(diskUsageIndicator);

      const reloadButton = this.__reloadButton = this.self().createToolbarButton().set({
        label: this.tr("Reload"),
        icon: "@FontAwesome5Solid/redo-alt/14",
        padding: [1, 5],
        gap: 10
      });
      reloadButton.addListener("execute", e => {
        this.fireEvent("restart");
      }, this);
      osparc.utils.Utils.setIdToWidget(reloadButton, "iFrameRestartBtn");
      buttonContainer.add(reloadButton);

      const zoomButton = this.__zoomButton = this.self().createToolbarButton().set({
        label: this.self().getZoomLabel(false),
        icon: this.self().getZoomIcon(false)
      });
      osparc.utils.Utils.setIdToWidget(zoomButton, this.self().getMaximizeWidgetId(false));
      zoomButton.addListener("execute", e => {
        this.maximizeIFrame(!this.hasState("maximized"));
      }, this);
      buttonContainer.add(zoomButton);

      appRoot.add(buttonContainer, {
        top: this.self().HIDDEN_TOP
      });
      standin.addListener("appear", e => {
        this.__syncIframePos();
      });
      standin.addListener("disappear", e => {
        iframe.setLayoutProperties({
          top: this.self().HIDDEN_TOP
        });
        buttonContainer.setLayoutProperties({
          top: this.self().HIDDEN_TOP
        });
      });
      this.addListener("move", e => {
        // got to let the new layout render first or we don't see it
        this.__syncIframePos();
      });
      this.addListener("resize", e => {
        // got to let the new layout render first or we don't see it
        this.__syncIframePos();
      });
      this.addListener("changeVisibility", e => {
        var visibility = e.getData()[0];
        if (visibility == "none") {
          iframe.set({
            zIndex: -10000
          });
        } else {
          this.__syncIframePos();
        }
      });
      return standin;
    },

    getIframe: function() {
      return this.__iframe;
    },

    getDiskUsageIndicator: function() {
      return this.__diskUsageIndicator;
    },

    maximizeIFrame: function(maximize) {
      if (maximize) {
        this.fireEvent("maximize");
        this.addState("maximized");
      } else {
        this.fireEvent("restore");
        this.removeState("maximized");
      }
      const actionButton = this.__zoomButton;
      actionButton.set({
        label: this.self().getZoomLabel(maximize),
        icon: this.self().getZoomIcon(maximize)
      });
      osparc.utils.Utils.setIdToWidget(actionButton, this.self().getMaximizeWidgetId(maximize));
      qx.event.message.Bus.getInstance().dispatchByName("maximizeIframe", this.hasState("maximized"));
    },

    __syncIframePos: function() {
      if (this.__syncScheduled) {
        return;
      }
      this.__syncScheduled = true;
      window.setTimeout(() => {
        this.__syncScheduled = false;
        let iframeParentPos = qx.bom.element.Location.get(qx.bom.element.Location.getOffsetParent(this.__iframe.getContentElement().getDomElement()), "scroll");
        const domElement = this.getContentElement().getDomElement();
        if (domElement === null) {
          return;
        }
        let divPos = qx.bom.element.Location.get(domElement, "scroll");
        let divSize = qx.bom.element.Dimension.getSize(domElement);
        this.__iframe.setLayoutProperties({
          top: divPos.top - iframeParentPos.top + this.getToolbarHeight(),
          left: divPos.left - iframeParentPos.left
        });
        this.__iframe.set({
          width: divSize.width,
          height: divSize.height - this.getToolbarHeight()
        });

        this.__buttonContainer.setLayoutProperties({
          top: (divPos.top - iframeParentPos.top),
          right: (iframeParentPos.right - iframeParentPos.left - divPos.right)
        });

        this.__buttonContainer.setVisibility(this.isShowToolbar() ? "visible" : "excluded");
      }, 0);
    },

    __applyShowToolbar: function(show) {
      this.setToolbarHeight(show ? 25 : 0);
      this.__syncIframePos();
    },

    _applySource: function(newValue) {
      this.__iframe.setSource(newValue);
    },

    // override
    _getIframeElement: function() {
      return this.__iframe._getIframeElement(); // eslint-disable-line no-underscore-dangle
    },

    /**
     * Cover the iframe with a transparent blocker div element. This prevents
     * pointer or key events to be handled by the iframe. To release the blocker
     * use {@link #release}.
     *
     */
    block : function() {
      this.__iframe.block();
    },

    /**
     * Release the blocker set by {@link #block}.
     *
     */
    release : function() {
      this.__iframe.release();
    }
  },

  destruct: function() {
    this.__iframe.exclude();
    this.__iframe.dispose();
    this.__iframe = undefined;
    qx.event.message.Bus.getInstance().unsubscribe("themeSwitch", this.themeSwitchHandler);
  }
});
