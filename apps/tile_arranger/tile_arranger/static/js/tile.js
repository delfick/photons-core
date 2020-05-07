import { Layer, Group, Rect, Line } from "react-konva";
import { useDispatch, useSelector } from "react-redux";
import { useState } from "react";

import { TileState } from "./state.js";

var TilePixels = ({ pixels, pixelWidth, tileWidth, lineWidth }) => (
  <Group>
    {pixels.map((pixel, j) => {
      var x = (j % 8) * pixelWidth;
      var y = Math.floor(j / 8) * pixelWidth;
      return (
        <Rect
          key={j}
          width={pixelWidth}
          height={pixelWidth}
          x={x}
          y={y}
          fill={pixel}
        />
      );
    })}
    <Line
      stroke="white"
      strokeWidth={lineWidth}
      points={[0, 0, tileWidth, 0, tileWidth, tileWidth, 0, tileWidth, 0, 0]}
    />
  </Group>
);

var Tile = ({ tile, zero_x, zero_y, pixelWidth, tileWidth }) => {
  var dispatch = useDispatch();

  var [position, setPosition] = useState({ x: 0, y: 0 });

  var start_x = zero_x + tile.user_x * pixelWidth;
  var start_y = zero_y - tile.user_y * pixelWidth;
  var lineWidth = Math.max(Math.floor(pixelWidth / 2), 1);

  var onDragEnd = () => {
    var left_x = (position.x - zero_x) / pixelWidth;
    var top_y = (zero_y - position.y) / pixelWidth;
    dispatch(
      TileState.ChangeCoords({
        serial: tile.serial,
        tile_index: tile.tile_index,
        left_x,
        top_y
      })
    );
  };

  var dragBound = pos => {
    var newpos = {
      x: pos.x - ((pos.x - zero_x) % pixelWidth),
      y: pos.y - ((pos.y - zero_y) % pixelWidth)
    };
    setPosition(newpos);
    return newpos;
  };

  return (
    <Group
      x={start_x}
      y={start_y}
      draggable={true}
      onDragEnd={onDragEnd}
      dragBoundFunc={dragBound}
      onClick={() =>
        dispatch(TileState.Highlight(tile.serial, tile.tile_index))
      }
      onTap={() => dispatch(TileState.Highlight(tile.serial, tile.tile_index))}
    >
      <TilePixels
        serial={tile.serial}
        pixels={tile.pixels}
        tile_index={tile.tile_index}
        pixelWidth={pixelWidth}
        lineWidth={lineWidth}
        tileWidth={tileWidth}
      />
    </Group>
  );
};

export default props => {
  var tiles = useSelector(state => state.tiles.tiles);

  return (
    <Layer>
      {tiles.map(tile => (
        <Tile key={tile.key} tile={tile} {...props} />
      ))}
    </Layer>
  );
};
