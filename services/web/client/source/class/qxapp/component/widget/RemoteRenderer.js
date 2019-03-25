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
 *   const link = new qxapp.component.widget.RemoteRenderer(webSocketUrl);
 *   this.getRoot().add(link);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.RemoteRenderer", {
  extend: qx.ui.core.Widget,

  construct: function(webSocketUrl) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
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
