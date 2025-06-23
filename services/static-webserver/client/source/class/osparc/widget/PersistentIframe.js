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

    this.__attachInterframeMessageHandlers();
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
      event: "changeShowToolbar",
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
    __buttonsContainer: null,
    __diskUsageIndicator: null,
    __reloadButton: null,
    __zoomButton: null,

    // override
    _createContentElement : function() {
      const iframe = this.__iframe = new qx.ui.embed.Iframe(this.getSource());
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

      const buttonsContainer = this.__buttonsContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignX: "right",
        alignY: "middle"
      }));

      const diskUsageIndicator = this.__diskUsageIndicator = new osparc.workbench.DiskUsageIndicator();
      diskUsageIndicator.getChildControl("disk-indicator").set({
        margin: 0
      });
      buttonsContainer.add(diskUsageIndicator);

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
      buttonsContainer.add(reloadButton);

      const zoomButton = this.__zoomButton = this.self().createToolbarButton().set({
        label: this.self().getZoomLabel(false),
        icon: this.self().getZoomIcon(false)
      });
      osparc.utils.Utils.setIdToWidget(zoomButton, this.self().getMaximizeWidgetId(false));
      zoomButton.addListener("execute", e => {
        this.maximizeIFrame(!this.hasState("maximized"));
      }, this);
      buttonsContainer.add(zoomButton);

      appRoot.add(buttonsContainer, {
        top: this.self().HIDDEN_TOP
      });
      standin.addListener("appear", e => {
        this.__syncIframePos();
      });
      standin.addListener("disappear", e => {
        iframe.setLayoutProperties({
          top: this.self().HIDDEN_TOP
        });
        buttonsContainer.setLayoutProperties({
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

        this.__buttonsContainer.setLayoutProperties({
          top: (divPos.top - iframeParentPos.top),
          right: (iframeParentPos.right - iframeParentPos.left - divPos.right)
        });

        this.__buttonsContainer.setVisibility(this.isShowToolbar() ? "visible" : "excluded");
      }, 0);
    },

    __applyShowToolbar: function(show) {
      this.setToolbarHeight(show ? 25 : 0);
      this.__syncIframePos();
    },

    _applySource: function(newValue) {
      this.__iframe.setSource(newValue);
    },

    __attachInterframeMessageHandlers: function() {
      this.__attachInterIframeThemeSyncer();
      this.__attachInterIframeListeners();
    },

    __attachInterIframeThemeSyncer: function() {
      this.postThemeSwitch = theme => {
        const msg = "osparc;theme=" + theme;
        this.sendMessageToIframe(msg);
      };

      this.themeSwitchHandler = msg => {
        this.postThemeSwitch(msg.getData());
      };
      qx.event.message.Bus.getInstance().subscribe("themeSwitch", this.themeSwitchHandler);
    },

    sendMessageToIframe: function(msg) {
      const iframe = this._getIframeElement();
      if (iframe) {
        const iframeDomEl = iframe.getDomElement();
        const iframeSource = iframe.getSource();
        if (iframeDomEl && iframeSource) {
          try {
            iframeDomEl.contentWindow.postMessage(msg, iframeSource);
          } catch (err) {
            console.log(`Failed posting message ${msg} to iframe ${iframeSource}\n${err.message}`);
          }
        }
      }
    },

    __attachInterIframeListeners: function() {
      this.__iframe.addListener("load", () => {
        const iframe = this._getIframeElement();
        if (iframe) {
          const iframeDomEl = iframe.getDomElement();
          const iframeSource = iframe.getSource();
          // Make sure the iframe is loaded and has a valid source
          if (iframeDomEl && iframeSource && iframeSource !== "about:blank") {
            window.addEventListener("message", message => {
              const data = message.data;
              if (data) {
                const origin = new URL(message.origin).hostname; // nodeId.services.deployment
                const nodeId = origin.split(".")[0];
                this.__handleIframeMessage(data, nodeId);
              }
            });
          }
        }
      }, this);
    },

    __handleIframeMessage: function(data, nodeId) {
      if (data["type"]) {
        switch (data["type"]) {
          case "theme": {
            // switch theme driven by the iframe
            const message = data["message"];
            if (message && message.includes("osparc;theme=")) {
              const themeName = message.replace("osparc;theme=", "");
              const validThemes = osparc.ui.switch.ThemeSwitcher.getValidThemes();
              const themeFound = validThemes.find(theme => theme.basename === themeName);
              const themeManager = qx.theme.manager.Meta.getInstance();
              if (themeFound !== themeManager.getTheme()) {
                themeManager.setTheme(themeFound);
              }
            }
            break;
          }
          case "openMarket": {
            if (osparc.product.Utils.showS4LStore()) {
              const category = data["message"] && data["message"]["category"];
              setTimeout(() => osparc.vipMarket.MarketWindow.openWindow(nodeId, category), 100);
            }
            break;
          }
          case "openWallets": {
            if (osparc.desktop.credits.Utils.areWalletsEnabled()) {
              setTimeout(() => osparc.desktop.credits.BillingCenterWindow.openWindow(), 100);
            }
            break;
          }
          case "openFunction": {
            // this is the MetaModeling service trying to show function/template information
            if (data["message"] && data["message"]["functionId"]) {
              const templateId = data["message"]["functionId"];
              const functionData = {
                "uuid": templateId,
                "resourceType": "function",
              };
              const resourceDetails = new osparc.dashboard.ResourceDetails(functionData).set({
                showOpenButton: false,
              });
              const win = osparc.dashboard.ResourceDetails.popUpInWindow(resourceDetails);
              win.setCaption("Function Details");
            }
            break;
          }
        }
      }
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
