.. _changelog:

ChangeLog
=========

0.9.5 - TBD
    * Make the dice roll work better with multiple tiles and the combine_tiles
      option
    * Made the falling animation much smoother. Many thanks to @mic159!

0.9.4 - 3 Jan 2019
    * Added get_tile_positions action
    * Adjustments to the dice font
    * Added the scripts used to generate photons_messages

0.9.3 - 30 December 2018
    * Minor changes
    * Another efficiency improvement for tile animations
    * Some fixes to the scrolling animations
    * Make it possible to combine many tiles into one animation

0.9.2 - 27 December 2018
    * Made tile_marquee work without options
    * Made animations on multiple tiles recalculate the whole animation for each
      tile even if they have the same user coords
    * Fixed tile_dice_roll to work when you have specified multiple tiles
    * Take into account the orientation of the tiles when doing animations
    * apply_theme action takes tile orientation into account
    * Made tile_falling and tile_nyan animations take in a random_orientation
      option for choosing random orientations for each tile

0.9.1 - 26 December 2018
    * Added tile_falling animation
    * Added tile_dice_roll animation
    * tile_marquee animation can now do dashes and underscores
    * Added a tile_dice script for putting 1 to 5 on your tiles
    * Made tile animations are lot less taxing on the CPU
    * Made tile_gameoflife animation default to using coords from the tiles
      rather than assuming the tiles are in a line.
    * Changed the defaults for animations to have higher refresh rate and not
      require acks on the messages
    * Made it possible to pause an animation if you've started it programatically

0.9.0 - 17 December 2018
    The photons_messages module is now generated via a process internal to LIFX.
    The information required for this will be made public but for now I'm making
    the resulting changes to photons.

    As part of this change there are some moves and renames to some messages.

    * ColourMessages is now LightMessages
    * LightPower messages are now under LightMessages
    * Infrared messages are now under LightMessages
    * Infrared messages now have `brightness` instead of `level`
    * Fixed Acknowledgement message typo
    * Multizone messages have better names

      * SetMultiZoneColorZones -> SetColorZones
      * GetMultiZoneColorZones -> GetColorZones
      * StateMultiZoneStateZones -> StateZone
      * StateMultiZoneStateMultiZones -> StateMultiZone

    * Tile messages have better names

      * GetTileState64 -> GetState64
      * SetTileState64 -> SetState64
      * StateTileState64 -> State64

    * Some reserved fields have more consistent names
    * SetWaveForm is now SetWaveform
    * SetWaveFormOptional is now SetWaveformOptional
    * num_zones field on multizone messages is now zones_count
    * The type field in SetColorZones was renamed to apply

0.8.1 - 2 December 2018
    * Added twinkles tile animation
    * Made it a bit easier to start animations programmatically

0.8.0 - 29 November 2018
    * Merging photons_script module into photons_control and photons_transport
    * Removing the need for the ATarget context manager and replacing it with a
      session() context manager on the target itself.

      So:

      .. code-block:: python

        from photons_script.script import ATarget
        async with ATarget(target) as afr:
            ...

      Becomes:

      .. code-block:: python

        async with target.session() as afr
            ...
    * Pipeline/Repeater/Decider is now in photons_control.script instead of
      photons_script.script.

0.7.1 - 29 November 2018
    * Made it easier to construct a SetWaveFormOptional
    * Fix handling of sockets when the network goes away

0.7.0 - 10 November 2018
    Moved code into ``photons_control`` and ``photons_messages``. This means
    ``photons_attributes``, ``photons_device_messages``, ``photons_tile_messages``
    and ``photons_transform`` no longer exist.

    Anything related to messages in those modules (and in ``photons_sockets.messages``
    is now in ``photons_messages``.

    Everything else in those modules, and the actions from ``photons_protocol``
    are now in ``photons_control``.

0.6.3 - 10 November 2018
    * Fix potential hang when connecting to a device (very unlikely error case,
      but now it's handled).
    * Moved the __or__ functionality on packets onto the LIFXPacket object as
      it's implementation depended on fields specifically on LIFXPacket. This
      is essentially a no-op within photons.
    * Added a create helper to TransportTarget

0.6.2 - 22 October 2018
    * Fixed cleanup logic
    * Make products registry aware of kelvin ranges
    * Made defaults for values in a message definition go through the spec for
      that field when no value is specified
    * Don't raise an error if we can't find any devices, instead respect the
      error_catcher option and only raise errors for not finding each serial that
      we couldn't find

0.6.1 - 1 September 2018
    * Added the tile_gameoflife task for doing a Conway's game of life simulation
      on your tiles.

0.6 - 26 August 2018
    * Cleaned up the code that handles retries and multiple replies

      - multiple_replies, first_send and first_wait are no longer options
        for run_with as they are no longer necessary
      - The packet definition now includes options for specifying how many
        packets to expect

    * When error_catcher to run_with is a callable, it is called straight away
      with all errors instead of being put onto the asyncio loop to be called
      soon. This means when you have awaited on run_with, you know that all
      errors have been given to the error_catcher
    * Remove uvloop altogether. I don't think it is actually necessary and it
      would break after the process was alive long enough. Also it's disabled
      for windows anyway, and something that needs to be compiled at
      installation.
    * collector.configuration["final_future"] is now the Future object itself
      rather than a function returning the future.
    * Anything inheriting from TransportTarget now has ``protocol_register``
      attribute instead of ``protocols`` and ``final_future`` instead of
      ``final_fut_finder``
    * Updated delfick_app to give us a --json-console-logs argument for showing
      logs as json lines

0.5.11 - 28 July 2018
    * Small fix to the version_number_spec for defining a version number on a
      protocol message
    * Made uvloop optional. To turn it off put ``photons_app: {use_uvloop: false}``
      in your configuration.

0.5.10 - 22 July 2018
    * Made version in StateHostFirmware and StateWifiFirmware a string instead
      of a float to tell the difference between "1.2" and "1.20"
    * Fix leaks of asyncio.Task objects

0.5.9 - 15 July 2018
    * Fixed a bug in the task runner such where a future could be given a result
      even though it was already done.
    * Made photons_app.helpers.ChildOfFuture behave as if it was cancelled when
      the parent future gets a non exception result. This is because ChildOfFuture
      is used to propagate errors/cancellation rather than propagate results.
    * Upgraded PyYaml and uvloop so that you can install this under python3.7
    * Fixes to make photons compatible with python3.7

0.5.8 - 1 July 2018
    * Fixed a bug I introduced in the Transformer in 0.5.7

0.5.7 - 1 July 2018
    * Fixed the FakeTarget in photons_app.test_helpers to deal with errors
      correctly
    * Made ``photons_transform.transformer.Transformer`` faster for most cases
      by making it not check the current state of the device when it doesn't
      need to

0.5.6 - 23 June 2018
    * photons_script.script.Repeater can now be stopped by raising Repater.Stop()
      in the on_done_loop callback
    * DeviceFinder can now be used to target specific serials

0.5.5 - 16 June 2018
    * Small fix to how as_dict() on a packet works so it does the right thing
      for packets that contain lists in the payload.
    * Added direction option to the marquee tile animation
    * Added nyan tile animation

0.5.4 - 28 April 2018
    * You can now specify ``("lifx.photon", "__all__")`` as a dependency and all
      photons modules will be seen as a dependency of your script.

      Note however that you should not do this in a module you expect to be used
      as a dependency by another module (otherwise you'll get cyclic dependencies).

0.5.3 - 22 April 2018
    * Tiny fix to TileState64 message

0.5.2 - 21 April 2018
    * Small fixes to the tile animations

0.5.1 - 31 March 2018
    * Tile animations
    * Added a ``serial`` property to packets that returns the hexlified target
      i.e. "d073d5000001" or None if target isn't set on the packet
    * Now installs and runs on Windows.

0.5 - 19 March 2018
    Initial opensource release after over a year of internal development.
