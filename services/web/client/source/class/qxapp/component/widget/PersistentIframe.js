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
  extend: "qx.ui.embed.Iframe",
  /**
   *
   * @param source {String} URL for the iframe content
   * @param poolEl {Element?} Dom node for attaching the iframe
   */
  construct: function(source, el) {
    if (el === null) {
      this.setIframePoolEl(el);
    }
    this.base(arguments, source);
  },
  properties :
  {
    /**
     * Source URL of the iframe.
     */
    iframePoolElement :
    {
      check : "Element",
      apply : "_applyIframePoolElement",
      init : window.documentElement
    }
  },
  members: {
    __iframe: null,
    _createContentElement : function() {
      var iframe = this.__iframe = this.base(arguments);
      var standin = new qx.html.Element("div");
      iframe.insertInto(this.getIframePoolEl());
      this.addListener("move", function(e) {
        var pos = e.getData();
        iframe.setStyles({
          top: pos.top,
          left: pos.left,
          width: pos.width,
          height: pos.height
        });
      }, this);
      this.addListener("changeVisibility", function(e) {
        var visibility = e.getData()[0];
        iframe.setStles({
          display: visibility == "visible" ? "inline":"none"
        });
      }, this);
      return standin;
    },
    _getIframeElement: function() {
      return this.__iframe;
    }
  }
});
