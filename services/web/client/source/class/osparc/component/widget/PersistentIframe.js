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

qx.Class.define("osparc.component.widget.PersistentIframe", {
  extend: qx.ui.embed.AbstractIframe,
  /**
   *
   * @param source {String} URL for the iframe content
   * @param poolEl {Element?} Dom node for attaching the iframe
   */
  construct: function(source, el) {
    this.base(arguments, source);
  },

  statics: {
    getIcon: function(maximize) {
      const iconURL = maximize ? "window-restore" : "window-maximize";
      return osparc.theme.osparcdark.Image.URLS[iconURL]+"/20";
    }
  },

  properties: {
    /**
     * Show a Maximize Button
     */
    showMaximize: {
      check: "boolean",
      init: false,
      apply: "_applyShowMaximize"
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
    __restartButton: null,
    __actionButton: null,
    // override
    _createContentElement : function() {
      let iframe = this.__iframe = new qx.ui.embed.Iframe(this.getSource());
      iframe.addListener("load", e => {
        this.fireEvent("load");
      });
      iframe.addListener("navigate", e => {
        this.fireDataEvent("navigate", e.getData());
      });

      let standin = new qx.html.Element("div");
      let appRoot = this.getApplicationRoot();
      appRoot.add(iframe, {
        top:-10000
      });
      const restartButton = this.__restartButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/redo-alt/14").set({
        zIndex: 20,
        paddingLeft: 8,
        paddingRight: 8,
        paddingTop: 6,
        paddingBottom: 6,
        backgroundColor: "transparent",
        decorator: null
      });
      restartButton.addListener("execute", e => {
        this.fireEvent("restart");
      }, this);
      osparc.utils.Utils.setIdToWidget(restartButton, "iFrameRestartBtn");
      appRoot.add(restartButton, {
        top:-10000
      });
      let actionButton = this.__actionButton = new qx.ui.form.Button(null).set({
        icon: this.self().getIcon(false),
        zIndex: 20,
        backgroundColor: "transparent",
        decorator: null
      });
      osparc.utils.Utils.setIdToWidget(actionButton, this.self().getMaximizeWidgetId(false));
      appRoot.add(actionButton, {
        top:-10000
      });
      actionButton.addListener("execute", e => {
        this.maximizeIFrame(!this.hasState("maximized"));
      }, this);
      appRoot.add(actionButton);
      standin.addListener("appear", e => {
        this.__syncIframePos();
      });
      standin.addListener("disappear", e => {
        iframe.setLayoutProperties({
          top: -10000
        });
        restartButton.setLayoutProperties({
          top: -10000
        });
        actionButton.setLayoutProperties({
          top: -10000
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

    maximizeIFrame: function(maximize) {
      const actionButton = this.__actionButton;
      if (maximize) {
        this.fireEvent("maximize");
        this.addState("maximized");
      } else {
        this.fireEvent("restore");
        this.removeState("maximized");
      }
      actionButton.setIcon(this.self().getIcon(maximize));
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
          top: divPos.top - iframeParentPos.top,
          left: (divPos.left - iframeParentPos.left)
        });
        this.__iframe.set({
          width: (divSize.width),
          height: (divSize.height)
        });
        this.__restartButton.setLayoutProperties({
          top: (divPos.top - iframeParentPos.top),
          right: (iframeParentPos.right - iframeParentPos.left - divPos.right) + 35
        });
        this.__actionButton.setLayoutProperties({
          top: (divPos.top - iframeParentPos.top),
          right: (iframeParentPos.right - iframeParentPos.left - divPos.right)
        });
      }, 0);
    },
    _applyShowMaximize: function(newValue, oldValue) {
      this._maximizeBtn.show();
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
  }
});
