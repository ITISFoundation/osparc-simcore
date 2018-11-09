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

qx.Class.define("qxapp.component.widget.PersistentIframe", {
  extend: qx.ui.embed.AbstractIframe,
  /**
   *
   * @param source {String} URL for the iframe content
   * @param poolEl {Element?} Dom node for attaching the iframe
   */
  construct: function(source, el) {
    this.base(arguments, source);
  },
  properties :
  {
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
    /** Fired if the iframe is restored from a minimized or maximized state */
    "restore" : "qx.event.type.Event",
    /** Fired if the iframe is maximized */
    "maximize" : "qx.event.type.Event"
  },
  members: {
    __iframe: null,
    __actionButton: null,
    // override
    _createContentElement : function() {
      let iframe = this.__iframe = new qx.ui.embed.Iframe(this.getSource()).set({
        zIndex: 1000
      });
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
      let actionButton = this.__actionButton = new qx.ui.form.Button(null, osparc.theme.osparcdark.Image.URLS["window-maximize"]+"/20").set({
        zIndex: 1001,
        backgroundColor: null,
        decorator: null
      });
      appRoot.add(actionButton, {
        top:-10000
      });
      actionButton.addListener("execute", e => {
        if (this.hasState("maximized")) {
          this.fireEvent("restore");
          this.removeState("maximized");
          actionButton.setIcon(osparc.theme.osparcdark.Image.URLS["window-maximize"]+"/20");
        } else {
          this.fireEvent("maximize");
          this.addState("maximized");
          actionButton.setIcon(osparc.theme.osparcdark.Image.URLS["window-restore"]+"/20");
        }
      });
      appRoot.add(actionButton);
      standin.addListener("appear", e => {
        this.__syncIframePos();
      });
      standin.addListener("disappear", e => {
        iframe.setLayoutProperties({
          top: -10000
        });
        actionButton.setLayoutProperties({
          top: -10000
        });
      });
      this.addListener("move", e => {
        // got to let the new layout render first or we don't see it
        qx.event.Timer.once(this.__syncIframePos, this, 0);
      });
      this.addListener("resize", e => {
        // got to let the new layout render first or we don't see it
        qx.event.Timer.once(this.__syncIframePos, this, 0);
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
    __syncIframePos: function() {
      let iframeParentPos = qx.bom.element.Location.get(qx.bom.element.Location.getOffsetParent(this.__iframe.getContentElement().getDomElement()), "scroll");
      let divPos = qx.bom.element.Location.get(this.getContentElement().getDomElement(), "scroll");
      let divSize = qx.bom.element.Dimension.getSize(this.getContentElement().getDomElement());
      this.__iframe.setLayoutProperties({
        top: divPos.top - iframeParentPos.top,
        left: (divPos.left - iframeParentPos.left)
      });
      this.__iframe.set({
        width: (divSize.width),
        height: (divSize.height)
      });
      this.__actionButton.setLayoutProperties({
        top: (divPos.top - iframeParentPos.top),
        right: (iframeParentPos.right - iframeParentPos.left - divPos.right)
      });
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
