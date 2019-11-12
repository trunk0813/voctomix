#!/usr/bin/env python3
import logging

from gi.repository import Gst

from lib.config import Config
from lib.clock import Clock
from lib.args import Args


class Blinder(object):
    log = logging.getLogger('Blinder')

    def __init__(self):
        self.acaps = Config.getAudioCaps()
        self.vcaps = Config.getVideoCaps()

        self.names = Config.getBlinderSources()
        self.log.info('Configuring Blinder video %u Sources',
                      len(self.names))

        self.volume = Config.getBlinderVolume()

        # Videomixer
        self.bin = """
bin.(
    name=blinder

    compositor
        name=compositor-blinder-mix
    ! tee
        name=video-mix-blinded

    video-mix.
    ! queue
        name=queue-video-mix-compositor-blinder-mix
    ! compositor-blinder-mix.
        """.format(
            vcaps=self.vcaps,
        )

        if Config.getSlidesSource():
            # add slides compositor
            self.bin += """
    compositor
        name=compositor-blinder-slides
    ! tee
        name=video-slides-blinded

    video-slides.
    ! queue
        name=queue-video-slides-compositor-blinder-slides
    ! compositor-blinder-slides.
            """

        for name in self.names:
            # Source from the named Blank-Video
            self.bin += """
    video-blinder-{name}.
    ! queue
        name=queue-video-blinder-{name}-compositor-blinder-mix
    ! compositor-blinder-mix.
            """.format(
                name=name
            )

            if Config.getSlidesSource():
                self.bin += """
    video-blinder-{name}.
    ! queue
        name=queue-video-blinder-{name}-compositor-blinder-slides
    ! compositor-blinder-slides.
            """.format(
                name=name
            )

        # Audiomixer
        self.bin += """
    audiomixer
        name=audiomixer-blinder
    ! tee
        name=audio-mix-blinded

    audio-mix.
    ! queue
        name=queue-audio-mix
    ! audiomixer-blinder.
            """.format(acaps=self.acaps)

        # Source from the Blank-Audio-Tee into the Audiomixer
        self.bin += """
    audio-blinder.
    ! queue
        name=queue-audio-blinded-audiomixer-blinder
    ! audiomixer-blinder.
"""

        self.bin += "\n)\n"

        self.blind_source = 0 if len(self.names) > 0 else None

    def __str__(self):
        return 'Blinder[{}]'.format(','.join(self.names))

    def attach(self,pipeline):
        self.pipeline = pipeline
        self.applyMixerState()

    def applyMixerState(self):
        self.applyMixerStateVideo('compositor-blinder-mix')
        if Config.getSlidesSource():
            self.applyMixerStateVideo('compositor-blinder-slides')
        self.applyMixerStateAudio('audiomixer-blinder')

    def applyMixerStateVideo(self, mixername):
        mixer = self.pipeline.get_by_name(mixername)
        if not mixer:
            self.log.error("Video mixer '%s' not found", mixername)
        else:
            mixer.get_static_pad('sink_0').set_property('alpha', int(self.blind_source is None))
            for idx, name in enumerate(self.names):
                blinder_pad = mixer.get_static_pad('sink_%u' % (idx + 1))
                blinder_pad.set_property('alpha', int(self.blind_source == idx))

    def applyMixerStateAudio(self, mixername):
        mixer = self.pipeline.get_by_name(mixername)
        if not mixer:
            self.log.error("Audio mixer '%s' not found", mixername)
        else:
            mixer.get_static_pad('sink_0').set_property('volume', 1.0 if self.blind_source is None else 0.0)
            mixer.get_static_pad('sink_1').set_property('volume', 0.0 if self.blind_source is None else 1.0)

    def setBlindSource(self, source):
        self.blind_source = source
        self.applyMixerState()