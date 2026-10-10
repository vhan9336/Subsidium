#include "fusion.h"

#include <algorithm>
#include <cmath>
#include <cstdio>

namespace so {

const char* toString(SensorStatus s) {
  switch (s) {
    case SensorStatus::Ok: return "OK";
    case SensorStatus::Suspect: return "SUSPECT";
    case SensorStatus::Failed: return "FAILED";
  }
  return "?";
}

const char* toString(AltSource s) {
  switch (s) {
    case AltSource::None: return "none";
    case AltSource::Rangefinder: return "rangefinder";
    case AltSource::Camera: return "camera";
    case AltSource::DeadReckoning: return "dead reckoning";
    case AltSource::Conservative: return "lower of rangefinder/camera";
  }
  return "?";
}

namespace {

std::string fmt(const char* f, double a, double b = 0) {
  char buf[200];
  std::snprintf(buf, sizeof buf, f, a, b);
  return buf;
}

SensorStatus classify(double health, SensorStatus prev) {
  if (health < 0.3) return SensorStatus::Failed;
  if (prev == SensorStatus::Failed && health < 0.7) return SensorStatus::Failed;
  return health < 0.65 ? SensorStatus::Suspect : SensorStatus::Ok;
}

}  // namespace

bool SecondOpinion::agree(double a, double b) const {
  return std::abs(a - b) <= p_.relTol * std::max(std::abs(a), std::abs(b)) + p_.absTol;
}

void SecondOpinion::setRangeHealth(double t, double h) {
  rangeHealth_ = std::clamp(h, 0.0, 1.0);
  const SensorStatus next = classify(rangeHealth_, rangeStatus_);
  if (next == rangeStatus_) return;
  if (next == SensorStatus::Failed)
    log(t, FusionEvent::Kind::Fault, "Rangefinder declared FAILED. Landing on the camera estimate.");
  else if (next == SensorStatus::Ok && rangeStatus_ == SensorStatus::Failed)
    log(t, FusionEvent::Kind::Good, "Rangefinder recovered and agrees with the camera again.");
  rangeStatus_ = next;
}

void SecondOpinion::setCameraHealth(double t, double h) {
  cameraHealth_ = std::clamp(h, 0.0, 1.0);
  const SensorStatus next = classify(cameraHealth_, cameraStatus_);
  if (next == cameraStatus_) return;
  if (next == SensorStatus::Failed)
    log(t, FusionEvent::Kind::Fault, "Camera declared unusable (no texture or inconsistent).");
  else if (next == SensorStatus::Ok && cameraStatus_ == SensorStatus::Failed)
    log(t, FusionEvent::Kind::Good, "Camera estimate usable again.");
  cameraStatus_ = next;
}

FusionOutput SecondOpinion::update(const FusionInput& in) {
  FusionOutput out;
  out.t = in.t;
  out.range = in.range;
  const double v = in.descentRate;

  const bool camValid = in.camera && in.camera->ttc && in.camera->confidence >= p_.minCamConfidence &&
                        v >= p_.minDescentRate;
  std::optional<double> camAlt;
  if (in.camera && in.camera->ttc) out.cameraTTC = in.camera->ttc;
  if (camValid) camAlt = *in.camera->ttc * v;
  out.cameraAltitude = camAlt;
  if (in.range && v >= p_.minDescentRate) out.rangeTTC = *in.range / v;

  if (!init_) {
    if (p_.initialAltitude >= 0) h_ = p_.initialAltitude;
    else if (in.range) h_ = *in.range;
    else if (camAlt) h_ = *camAlt;
    else {
      out.verdict = "Waiting for a first altitude reading";
      return out;
    }
    init_ = true;
    lastT_ = in.t;
  }

  const double dt = std::max(0.0, in.t - lastT_);
  lastT_ = in.t;
  const double hPred = std::max(0.0, h_ - v * dt);
  out.deadReckoning = hPred;

  // Camera health: does it see enough texture to judge?
  if (in.camera) {
    const double c = in.camera->confidence;
    setCameraHealth(in.t, cameraHealth_ + (c >= p_.minCamConfidence ? p_.healthUp : -p_.healthDown) * dt);
  } else if (v >= p_.minDescentRate) {
    setCameraHealth(in.t, cameraHealth_ - 0.2 * dt);
  }

  std::optional<double> accepted;
  bool reset = false, conservative = false;
  std::string verdict;

  if (!in.range) {
    setRangeHealth(in.t, rangeHealth_ - p_.healthDown * dt);
    if (!missingLogged_) {
      log(in.t, FusionEvent::Kind::Warn, "Rangefinder returned no reading.");
      missingLogged_ = true;
    }
    verdict = camValid ? "No rangefinder data. Flying on the camera estimate."
                       : "No rangefinder data and no usable camera. Dead reckoning only.";
  } else {
    missingLogged_ = false;
    const double r = *in.range;
    const bool consistent = std::abs(r - hPred) <= std::max(p_.gateAbs, p_.gateRel * hPred);

    // Brief spikes that vanish on their own are spurious returns. A few
    // per second means a noisy sensor rather than terrain.
    if (consistent && pending_ && !pending_->rejected && in.t - pending_->start < 0.5) spikes_.push_back(in.t);
    while (!spikes_.empty() && spikes_.front() < in.t - 3) spikes_.pop_front();
    if (!noisy_ && spikes_.size() >= 3) {
      noisy_ = true;
      log(in.t, FusionEvent::Kind::Warn, "Rangefinder is returning spurious spikes. Filtering them against the camera.");
    } else if (noisy_ && spikes_.empty()) {
      noisy_ = false;
      log(in.t, FusionEvent::Kind::Info, "Rangefinder spikes have stopped.");
    }
    if (noisy_) setRangeHealth(in.t, std::min(rangeHealth_, 0.6));

    if (consistent) {
      if (pending_ && pending_->rejected)
        log(in.t, FusionEvent::Kind::Info, "Rangefinder back in line with the predicted altitude.");
      pending_.reset();
      if (camValid && !agree(r, *camAlt)) disagreeTime_ += dt;
      else disagreeTime_ = 0;

      if (disagreeTime_ > p_.confirmWindow) {
        // The rangefinder moves the way the IMU says, but the camera puts
        // the ground somewhere else. Two of three agree only because dead
        // reckoning is anchored to the rangefinder, so we can't tell who is
        // wrong. Assume the ground is closer: slowing early is survivable.
        if (disagreeTime_ - dt <= p_.confirmWindow)
          log(in.t, FusionEvent::Kind::Warn,
              fmt("Rangefinder (%.1f m) and camera (%.1f m) disagree but both look self-consistent. "
                  "Using the lower one.", r, *camAlt));
        conservative = true;
        accepted = r;
        setCameraHealth(in.t, cameraHealth_ - 0.3 * dt);
        setRangeHealth(in.t, rangeHealth_ - 0.3 * dt);
        verdict = "Rangefinder and camera disagree. Assuming the ground is closer.";
      } else {
        accepted = r;
        setRangeHealth(in.t, rangeHealth_ + p_.healthUp * dt);
        if (noisy_) setRangeHealth(in.t, std::min(rangeHealth_, 0.6));
        verdict = noisy_ ? "Rangefinder noisy: keeping only readings that match motion and camera."
                : camValid ? (agree(r, *camAlt) ? "Rangefinder and camera agree." : "Rangefinder and camera drifting apart, watching.")
                           : "Rangefinder consistent with motion (camera has no opinion).";
      }
    } else {
      if (!pending_) {
        pending_ = Pending{in.t, hPred};
        if (!noisy_) log(in.t, FusionEvent::Kind::Warn,
            fmt("Rangefinder jumped from %.2f m to %.2f m. Asking the camera.", hPred, r));
      }
      const double waited = in.t - pending_->start;
      // A real terrain change persists; a lone spike that happens to match
      // the camera must not reset the altitude.
      if (camValid && agree(r, *camAlt) && waited >= 0.25) {
        if (!noisy_) log(in.t, FusionEvent::Kind::Good,
            fmt("Camera agrees with the new reading (%.2f m vs %.2f m): the terrain changed. Keeping it.", *camAlt, r));
        accepted = r;
        reset = true;
        pending_.reset();
        setRangeHealth(in.t, rangeHealth_ + 0.5);
        verdict = "Terrain change confirmed by camera.";
      } else if (waited > p_.confirmWindow &&
                 (!camValid || agree(*camAlt, hPred) || waited > 2 * p_.confirmWindow)) {
        // Reject when the camera sides with the prediction (2 of 3 against
        // the rangefinder), or when nothing has confirmed the jump for a
        // long time. A camera that matches neither is not evidence either way.
        if (!pending_->rejected) {
          pending_->rejected = true;
          log(in.t, camValid ? FusionEvent::Kind::Fault : FusionEvent::Kind::Warn,
              camValid ? fmt("Camera still says %.2f m, not %.2f m. Rejecting the rangefinder.", *camAlt, r)
                       : fmt("No camera opinion available. Rejecting the %.2f m reading.", r));
        }
        setRangeHealth(in.t, rangeHealth_ - p_.healthDown * dt);
        verdict = camValid ? "Camera contradicts the rangefinder. Rangefinder rejected."
                           : "Rangefinder jump unverifiable. Rejected.";
      } else {
        verdict = fmt("Rangefinder jump: waiting for the camera (%.1f s).", waited);
      }
    }
  }

  // Altitude update.
  const bool trustRange = rangeStatus_ != SensorStatus::Failed;
  if (accepted && trustRange) {
    if (conservative && camAlt) {
      h_ = std::min(hPred + p_.rangeBlend * (*accepted - hPred), *camAlt);
      out.source = AltSource::Conservative;
    } else {
      h_ = reset ? *accepted : hPred + p_.rangeBlend * (*accepted - hPred);
      out.source = AltSource::Rangefinder;
    }
  } else if (camValid) {
    // Bounded pull: a sustained disagreement still converges within a few
    // seconds, but one glitchy frame (TTC spikes when the expansion rate
    // briefly reads ~0) can only nudge the estimate.
    const double a = 1 - std::exp(-dt * in.camera->confidence / p_.cameraTau);
    const double maxStep = 0.3 * hPred + p_.absTol;
    h_ = hPred + a * std::clamp(*camAlt - hPred, -maxStep, maxStep);
    out.source = AltSource::Camera;
  } else {
    h_ = hPred;
    out.source = AltSource::DeadReckoning;
    if (!blindLogged_ && in.range == std::nullopt) {
      log(in.t, FusionEvent::Kind::Fault, "No working altitude sensor. Dead reckoning only.");
      blindLogged_ = true;
    }
  }
  if (out.source != AltSource::DeadReckoning) blindLogged_ = false;
  if (accepted && !trustRange) verdict = "Rangefinder looks sane again but stays benched until it proves itself.";

  h_ = std::max(0.0, h_);
  out.altitude = h_;
  out.rangeHealth = rangeHealth_;
  out.cameraHealth = cameraHealth_;
  out.rangeStatus = rangeStatus_;
  out.cameraStatus = cameraStatus_;
  out.jumpPending = pending_.has_value() && !pending_->rejected;
  out.verdict = verdict;
  return out;
}

FusionOutput BaselineEstimator::update(const FusionInput& in) {
  FusionOutput out;
  out.t = in.t;
  out.range = in.range;
  const double v = in.descentRate;
  if (in.range && v >= p_.minDescentRate) out.rangeTTC = *in.range / v;

  if (!init_) {
    if (p_.initialAltitude >= 0) h_ = p_.initialAltitude;
    else if (in.range) h_ = *in.range;
    else {
      out.verdict = "Waiting for a first altitude reading";
      return out;
    }
    init_ = true;
    lastT_ = in.t;
  }
  const double dt = std::max(0.0, in.t - lastT_);
  lastT_ = in.t;
  const double hPred = std::max(0.0, h_ - v * dt);
  out.deadReckoning = hPred;

  if (lockedOut_) {
    h_ = hPred;
    out.source = AltSource::DeadReckoning;
    out.rangeStatus = SensorStatus::Failed;
    out.verdict = "Rangefinder judged abnormal earlier. Using calculated altitude.";
  } else if (!in.range) {
    h_ = hPred;
    out.source = AltSource::DeadReckoning;
    out.verdict = "No rangefinder data. Using calculated altitude.";
    if (!missingLogged_) {
      events_.push_back({in.t, FusionEvent::Kind::Warn, "Rangefinder returned no reading."});
      missingLogged_ = true;
    }
  } else {
    missingLogged_ = false;
    const double r = *in.range;
    if (std::abs(r - hPred) <= std::max(p_.gateAbs, p_.gateRel * hPred)) {
      h_ = hPred + p_.rangeBlend * (r - hPred);
      rejectTime_ = 0;
      out.source = AltSource::Rangefinder;
      out.verdict = "Rangefinder within expected range.";
    } else {
      if (rejectTime_ == 0 && in.t - lastRejectLog_ > 2.0) {
        lastRejectLog_ = in.t;
        events_.push_back({in.t, FusionEvent::Kind::Warn,
                           fmt("Rangefinder reading %.2f m too far from expected %.2f m. Rejected.", r, hPred)});
      }
      rejectTime_ += dt;
      h_ = hPred;
      out.source = AltSource::DeadReckoning;
      out.rangeStatus = SensorStatus::Suspect;
      out.verdict = "Rangefinder reading rejected.";
      if (rejectTime_ > 1.0) {
        lockedOut_ = true;
        events_.push_back({in.t, FusionEvent::Kind::Fault,
                           "Rangefinder judged abnormal. Ignoring it for the rest of the descent."});
      }
    }
  }
  h_ = std::max(0.0, h_);
  out.altitude = h_;
  out.rangeHealth = lockedOut_ ? 0 : 1;
  out.cameraHealth = 0;
  return out;
}

}  // namespace so
