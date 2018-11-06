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
  extend: qx.ui.embed.Iframe,
  /**
   *
   * @param source {String} URL for the iframe content
   * @param poolEl {Element?} Dom node for attaching the iframe
   */
  construct: function(source, el) {
    this.setIframePoolElement(el||qx.dom.Node.getBodyElement(window));
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
      apply : "_applyIframePoolElement"
    }
  },
  members: {
    __iframe: null,
    // override
    _createContentElement : function() {
      let iframe = this.__iframe = this.base(arguments);
      let standin = new qx.html.Element("div");
      let syncPos = function syncPos() {
        let iframeParentPos = qx.bom.element.Location.get(qx.bom.element.Location.getOffsetParent(iframe.getDomElement()),'scroll');
        let divPos = qx.bom.element.Location.get(standin.getDomElement(),'scroll');
        let divSize = qx.bom.element.Dimension.getSize(standin.getDomElement());
        iframe.setStyles({
          top: (divPos.top - iframeParentPos.top) + "px",
          left: (divPos.left - iframeParentPos.left) + "px",
          width: divSize.width + "px",
          height: divSize.height + "px"
        });
      };
      standin.addListenerOnce("appear", e => {
        qx.dom.Element.insertEnd(iframe.getDomElement(), this.getIframePoolElement());
      });
      standin.addListener("appear", e => {
        iframe.setStyles({
          position: "absolute",
          zIndex: 100
        });
        syncPos();
      });
      standin.addListener("disappear",e =>{
        iframe.setStyles({
          zIndex: -10000
        });
      });
      standin.addListener("move", e => syncPos);
      standin.addListener("changeVisibility", e => {
        var visibility = e.getData()[0];
        if (visibility == "none"){
          iframe.setStyles({
            zIndex: -10000
          });
        }
        else {
          syncPos();
        }
      });
      return standin;
    },
    _applyIframePoolElement: function(newValue, oldValue) {
      if (this.__iframe && newValue !== oldValue) {
        this.__iframe.insertInto(newValue);
      }
    },
    // override
    _getIframeElement: function() {
      return this.__iframe;
    }
  },
  destruct: function() {
    this.__iframe.exclude();
    this.__iframe.dispose();
    this.__iframe = undefined;
  }
});
