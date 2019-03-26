/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * A Canvas that renders the given jpeg image and sends pointer interactions to backend
 * via websocket
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const remoteRenderer = new qxapp.component.widget.RemoteRenderer(node, webSocketUrl);
 *   this.getRoot().add(remoteRenderer);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.RemoteRenderer", {
  extend: qx.ui.core.Widget,

  /**
    * @param node {qxapp.data.model.Node} Node owning the widget
    * @param webSocketUrl {string} webSocketUrl
  */
  construct: function(node, webSocketUrl) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      node: node,
      webSocketUrl: webSocketUrl
    });

    this.addListenerOnce("appear", () => {
      const elem = this.getContentElement().getDomElement();
      const events = [
        "pointerdown",
        "pointerup",
        "tap",
        "dbltap",
        "longtap",
        "pointermove",
        "pointerover",
        "pointerout",
        "swipe",
        "track",
        "rotate",
        "pinch"
      ];
      events.forEach(event => {
        qx.bom.Element.addListener(elem, event, this.__logPointerEvent, this);
      }, this);
    }, this);
  },

  properties: {
    node: {
      check: "qxapp.data.model.Node",
      nullable: false
    },

    webSocketUrl: {
      check: "String",
      nullable: true
    }
  },

  members: {
    __logPointerEvent: function(pointerEvent) {
      pointerEvent.preventDefault();

      const evType = pointerEvent.getType();
      const evButton = pointerEvent.getButton();
      const evXPos = pointerEvent.getDocumentLeft();
      const evYPos = pointerEvent.getDocumentTop();
      const docWidth = this.getBounds().width;
      const docHeight = this.getBounds().height;
      const evXPosRel = evXPos / docWidth;
      const evYPosRel = evYPos / docHeight;
      console.log(evType, evButton, evXPos, evYPos, evXPosRel, evYPosRel);
    }
  }
});
