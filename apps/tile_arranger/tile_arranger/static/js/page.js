import { ReactReduxContext, Provider } from "react-redux";
import { useEffect, useState, useReducer } from "react";
import { Stage, Layer, Rect, Line } from "react-konva";

import Tiles from "./tile.js";

function getPos(el) {
  for (
    var lx = 0, ly = 0;
    el != null;
    lx += el.offsetLeft, ly += el.offsetTop, el = el.offsetParent
  );
  return { x: lx, y: ly };
}

function x_y_for_evt(evt, offset) {
  var s_x, s_y;
  if (evt.clientX === undefined) {
    s_x = evt.changedTouches[0].clientX - offset.x;
    s_y = evt.changedTouches[0].clientY - offset.y;
  } else {
    s_x = evt.clientX - offset.x;
    s_y = evt.clientY - offset.y;
  }
  return [s_x, s_y];
}

function makeGrid(dimensions, zerosState) {
  var { tileWidth, height, width } = dimensions;

  var grid = [
    <Line
      key="centerx0"
      strokeWidth={2}
      stroke="red"
      points={[zerosState.zero_x, 0, zerosState.zero_x, height]}
    />,
    <Line
      key="centery0"
      strokeWidth={2}
      stroke="red"
      points={[0, zerosState.zero_y, width, zerosState.zero_y]}
    />
  ];

  for (
    var i = zerosState.zero_x + tileWidth;
    i <= width + tileWidth * 2;
    i += tileWidth
  ) {
    if (i > 0) {
      grid.push(
        <Line
          key={"rcol" + i}
          strokeWidth={1}
          stroke="#868686"
          points={[i, 0, i, height]}
        />
      );
    }
  }

  for (
    var i = zerosState.zero_x - tileWidth;
    i >= -tileWidth * 2;
    i -= tileWidth
  ) {
    if (i < width) {
      grid.push(
        <Line
          key={"lcol" + i}
          strokeWidth={1}
          stroke="#868686"
          points={[i, 0, i, height]}
        />
      );
    }
  }

  for (
    var i = zerosState.zero_y + tileWidth;
    i <= height + tileWidth * 2;
    i += tileWidth
  ) {
    if (i > 0) {
      grid.push(
        <Line
          key={"trow" + i}
          strokeWidth={1}
          stroke="#868686"
          points={[0, i, width, i]}
        />
      );
    }
  }

  for (
    var i = zerosState.zero_y - tileWidth;
    i >= -tileWidth * 2;
    i -= tileWidth
  ) {
    if (i < height) {
      grid.push(
        <Line
          key={"bcol" + i}
          strokeWidth={1}
          stroke="#868686"
          points={[0, i, width, i]}
        />
      );
    }
  }

  return grid;
}

export default () => {
  var makeDimensions = () => {
    var width = Math.max(
      document.documentElement.clientWidth,
      window.innerWidth || 0
    );
    var height = Math.max(
      document.documentElement.clientHeight,
      window.innerHeight || 0
    );
    var pixelWidth = Math.max(Math.ceil(window.innerWidth / 160), 6);
    var tileWidth = pixelWidth * 8;
    return {
      width,
      height,
      pixelWidth,
      tileWidth
    };
  };
  const [dimensions, setDimensions] = useState(makeDimensions());

  var zeroReducer = (state, action) => {
    const offset = getPos(action.e.target.getStage().attrs.container);
    const [s_x, s_y] = x_y_for_evt(action.e.evt, offset);

    switch (action.type) {
      case "drag_grid_start":
        return {
          ...state,
          grid_x: s_x,
          grid_y: s_y,
          start_offset: { zero_x: state.zero_x, zero_y: state.zero_y }
        };
      case "drag_grid":
        var diffx = state.grid_x - s_x;
        var diffy = state.grid_y - s_y;
        return {
          ...state,
          zero_x: state.start_offset.zero_x - diffx,
          zero_y: state.start_offset.zero_y - diffy
        };
      default:
        throw new Error(`Unknown event ${action.type}`);
    }
  };

  var width = dimensions.width;
  var height = dimensions.height;

  var zero_x = Math.floor(width / 2);
  var zero_y = Math.floor(height / 2);

  const [zerosState, dispatchZeros] = useReducer(zeroReducer, {
    zero_x,
    zero_y,
    grid_x: 0,
    grid_y: 0,
    start_offset: { zero_x, zero_y }
  });

  useEffect(() => {
    function handleResize() {
      setDimensions(makeDimensions());
    }

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  var zero_x = Math.floor(width / 2);
  var zero_y = Math.floor(height / 2) - 100;

  return (
    <ReactReduxContext.Consumer>
      {({ store }) => (
        <Stage width={width} height={height} fill="red">
          <Provider store={store}>
            <Layer>
              <Rect
                width={width}
                height={height}
                fill="#e6e6e6"
                draggable={true}
                dragBoundFunc={_ => ({ x: 0, y: 0 })}
                onDragMove={e => dispatchZeros({ type: "drag_grid", e })}
                onDragStart={e => dispatchZeros({ type: "drag_grid_start", e })}
              />
            </Layer>
            <Layer>{makeGrid(dimensions, zerosState)}</Layer>
            <Tiles
              zero_x={zerosState.zero_x}
              zero_y={zerosState.zero_y}
              pixelWidth={dimensions.pixelWidth}
              tileWidth={dimensions.tileWidth}
            />
          </Provider>
        </Stage>
      )}
    </ReactReduxContext.Consumer>
  );
};
