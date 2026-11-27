
import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Check,
  CheckCircle2,
  CircleDollarSign,
  Compass,
  Lightbulb,
  Network,
  ShieldCheck,
  Target,
  TrendingUp,
  Users,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { MobileMenu } from "@/components/landing/MobileMenu";

import "./landing.css";

const FEATURES: {
  number: string;
  eyebrow: string;
  title: string;
  description: string;
  footer: string;
  icon: LucideIcon;
}[] = [
    {
      number: "01",
      eyebrow: "DISCOVER",
      title: "Innovation readiness",
      description:
        "Bring your team together to assess 60 statements across 12 innovation dimensions and agree a readiness score out of 300.",
      footer: "Understand where you stand",
      icon: BarChart3,
    },
    {
      number: "02",
      eyebrow: "EVALUATE",
      title: "Idea IQ & Value for Money",
      description:
        "Evaluate ideas with Innovation Quotient scoring and Value for Money analysis to support better investment decisions.",
      footer: "Compare with confidence",
      icon: Target,
    },
    {
      number: "03",
      eyebrow: "COLLABORATE",
      title: "Built for collaboration",
      description:
        "Invite team members, agree assessment answers, and give consultants time-limited read-only access.",
      footer: "Move forward together",
      icon: Users,
    },
  ];

const AUDIENCES: {
  number: string;
  name: string;
  description: string;
  icon: LucideIcon;
  detail: string;
}[] = [
    {
      number: "01",
      name: "Innovators",
      description:
        "Validate ideas before investing valuable time and resources.",
      icon: Lightbulb,
      detail: "Validate potential",
    },
    {
      number: "02",
      name: "R&D leaders",
      description:
        "Prioritise innovation opportunities with greater clarity.",
      icon: Network,
      detail: "Prioritise opportunities",
    },
    {
      number: "03",
      name: "Procurement",
      description:
        "Evaluate value for money with more confidence.",
      icon: CircleDollarSign,
      detail: "Evaluate value",
    },
    {
      number: "04",
      name: "Investors",
      description:
        "Compare opportunities using structured insights.",
      icon: TrendingUp,
      detail: "Compare opportunities",
    },
  ];

function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link
      href="/"
      className="landing-logo"
      aria-label="InnoValuation home"
    >
      <Image
        src="/innovaluation-mark.png"
        alt=""
        width={42}
        height={42}
        priority
      />
      <span className={light ? "landing-logo-light" : ""}>
        Inno<span>Valuation</span>
      </span>
    </Link>
  );
}

function Header() {
  return (
    <header className="landing-header">
      <div className="landing-container landing-header-inner">
        <Logo light />

        <nav
          className="landing-desktop-nav"
          aria-label="Main navigation"
        >
          <a href="#how-it-works">How it works</a>
          <a href="#features">Features</a>
          <a href="#who-its-for">Who it&apos;s for</a>
        </nav>


        <MobileMenu className="landing-mobile-menu">
          <summary
            className="landing-mobile-menu-trigger"
            aria-label="Toggle navigation menu"
          >
            <span className="landing-mobile-menu-icon" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          </summary>

          <nav className="landing-mobile-dropdown" aria-label="Mobile navigation">
            <div className="landing-mobile-dropdown-heading">
              EXPLORE INNOVALUATION
            </div>

            <a href="#how-it-works">How it works</a>
            <a href="#features">Features</a>
            <a href="#who-its-for">Who it&apos;s for</a>

            <div className="landing-mobile-dropdown-divider" />

            <Link href="/sign-in">Sign in</Link>

            <Link href="/sign-up" className="landing-mobile-dropdown-cta">
              Get started
              <span aria-hidden="true">↗</span>
            </Link>
          </nav>
        </MobileMenu>

        <div className="landing-header-actions">
          <Link href="/sign-in" className="landing-signin">
            Sign in
          </Link>

          <Link href="/sign-up" className="landing-button landing-button-gold">
            Get started <ArrowUpRight size={17} />
          </Link>
        </div>
      </div>
    </header>
  );
}

function InnovationCompass() {
  return (
    <div className="landing-compass-stage" aria-hidden="true">
      <div className="landing-compass-halo" />

      <svg
        className="landing-compass-svg"
        viewBox="0 0 440 440"
        fill="none"
      >
        <circle
          cx="220"
          cy="220"
          r="202"
          stroke="#DDB66C"
          strokeOpacity=".75"
          strokeWidth="1.4"
        />
        <circle
          cx="220"
          cy="220"
          r="185"
          stroke="#DDB66C"
          strokeOpacity=".27"
          strokeDasharray="2 9"
        />
        <circle
          cx="220"
          cy="220"
          r="151"
          stroke="#9EACC0"
          strokeOpacity=".33"
        />
        <circle
          cx="220"
          cy="220"
          r="111"
          stroke="#9EACC0"
          strokeOpacity=".19"
          strokeDasharray="4 9"
        />

        {Array.from({ length: 48 }, (_, index) => {
          const angle = (index * Math.PI) / 24;
          const major = index % 4 === 0;
          const inner = major ? 176 : 185;
          const outer = 197;
          return (
            <line
              key={index}
              x1={220 + Math.sin(angle) * inner}
              y1={220 - Math.cos(angle) * inner}
              x2={220 + Math.sin(angle) * outer}
              y2={220 - Math.cos(angle) * outer}
              stroke={major ? "#DDB66C" : "#8291AA"}
              strokeOpacity={major ? ".9" : ".5"}
              strokeWidth={major ? "2.5" : "1"}
            />
          );
        })}

        <g className="landing-compass-rose">
          <path d="M220 62L241 199L220 220Z" fill="#F0F4FA" />
          <path d="M220 62L199 199L220 220Z" fill="#8196B5" />
          <path d="M378 220L241 241L220 220Z" fill="#F0F4FA" />
          <path d="M378 220L241 199L220 220Z" fill="#A7B7CD" />
          <path d="M220 378L199 241L220 220Z" fill="#F0F4FA" />
          <path d="M220 378L241 241L220 220Z" fill="#8296B5" />
          <path d="M62 220L199 199L220 220Z" fill="#E7ECF5" />
          <path d="M62 220L199 241L220 220Z" fill="#8296B5" />

          <path d="M145 145L211 211L220 220Z" fill="#516B90" />
          <path d="M295 145L229 211L220 220Z" fill="#6E85A6" />
          <path d="M295 295L229 229L220 220Z" fill="#516B90" />
          <path d="M145 295L211 229L220 220Z" fill="#6E85A6" />
        </g>

        <g className="landing-compass-needle">
          <path
            d="M220 220L362 79L339 137Z"
            fill="#DDB66C"
          />
          <path
            d="M220 220L79 362L137 339Z"
            fill="#D66E59"
          />
          <circle cx="220" cy="220" r="20" fill="#DDB66C" />
          <circle cx="220" cy="220" r="12" fill="#071120" />
          <circle cx="220" cy="220" r="5" fill="#D66E59" />
        </g>
      </svg>

      <div className="landing-compass-label label-top">12</div>
      <div className="landing-compass-label label-right">03</div>
      <div className="landing-compass-label label-bottom">06</div>
      <div className="landing-compass-label label-left">09</div>

      <span className="landing-orbit-caption">
        NAVIGATE YOUR INNOVATION POTENTIAL
      </span>
    </div>
  );
}

function HeroIntelligenceCard() {
  return (
    <div className="landing-intelligence-card">
      <div className="landing-intelligence-top">
        <span>
          <span className="landing-live-dot" />
          INNOVATION FRAMEWORK
        </span>
        <Compass size={16} />
      </div>

      <div className="landing-intelligence-body">
        <div>
          <span className="landing-intelligence-label">
            Dimensions of innovation
          </span>
          <div className="landing-intelligence-value">
            12 <span>dimensions</span>
          </div>
        </div>

        <div className="landing-intelligence-progress">
          {Array.from({ length: 12 }, (_, index) => (
            <span key={index} />
          ))}
        </div>

        <p>
          A structured framework for evaluating innovation
          readiness and opportunity.
        </p>
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section className="landing-hero">
      <div className="landing-container landing-hero-inner">
        <div className="landing-hero-copy">
          <div className="landing-hero-kicker">
            <span />
            NAVIGATE · MEASURE · INNOVATE
          </div>

          <h1>
            Innovation
            <span className="landing-outline-text"> you can</span>
            <span className="landing-gold-text"> measure.</span>
          </h1>

          <p className="landing-hero-description">
            Great ideas deserve measurable impact. Understand your
            organisation&apos;s innovation readiness, evaluate ideas
            with confidence, and turn opportunities into informed
            decisions.
          </p>

          <div className="landing-hero-actions">
            <Link
              href="/sign-up"
              className="landing-button landing-button-gold"
            >
              Start your innovation journey
              <ArrowUpRight size={19} />
            </Link>

            <a
              href="#how-it-works"
              className="landing-button landing-button-outline"
            >
              Explore the platform
              <ArrowRight size={18} />
            </a>
          </div>

          <div className="landing-trust-strip">
            <div>
              <CheckCircle2 size={17} />
              <span>12 innovation dimensions</span>
            </div>
            <div>
              <ShieldCheck size={17} />
              <span>Structured evaluations</span>
            </div>
            <div>
              <Users size={17} />
              <span>Team collaboration</span>
            </div>
          </div>
        </div>

        <div className="landing-hero-visual">
          <InnovationCompass />
          <HeroIntelligenceCard />

          <div className="landing-floating-marker">
            <Zap size={15} />
            <span>Innovation intelligence</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function FeatureVisual({ index }: { index: number }) {
  if (index === 0) {
    return (
      <div className="landing-feature-visual" aria-hidden="true">
        <div className="landing-mini-top">
          <span>READINESS ANALYSIS</span>
          <BarChart3 size={17} />
        </div>

        <div className="landing-chart">
          {[42, 67, 54, 81, 62, 94, 76].map((height, i) => (
            <div className="landing-chart-track" key={i}>
              <span
                style={{
                  height: `${height}%`,
                  animationDelay: `${i * 90}ms`,
                }}
              />
            </div>
          ))}
        </div>

        <div className="landing-mini-bottom">
          <span>Understand your potential</span>
          <TrendingUp size={16} />
        </div>
      </div>
    );
  }

  if (index === 1) {
    return (
      <div className="landing-feature-visual" aria-hidden="true">
        <div className="landing-mini-top">
          <span>IDEA INTELLIGENCE</span>
          <Target size={17} />
        </div>

        <div className="landing-iq-visual">
          <div className="landing-iq-ring">
            <div>
              <span>IDEA</span>
              <strong>IQ</strong>
            </div>
          </div>

          <div className="landing-iq-details">
            <span>Structured evaluation</span>
            <strong>Compare ideas with clarity</strong>
            <div className="landing-iq-line"><span /></div>
            <div className="landing-iq-line"><span /></div>
          </div>
        </div>

        <div className="landing-mini-bottom">
          <span>Innovation Quotient · Value for Money</span>
          <ArrowUpRight size={16} />
        </div>
      </div>
    );
  }

  return (
    <div className="landing-feature-visual" aria-hidden="true">
      <div className="landing-mini-top">
        <span>TEAM WORKSPACE</span>
        <Network size={17} />
      </div>

      <div className="landing-network">
        <svg viewBox="0 0 300 120" fill="none">
          <path
            d="M65 60L150 25L235 60L150 95Z"
            stroke="#9AAEC9"
            strokeWidth="1.5"
            strokeDasharray="5 5"
          />
          <path
            d="M65 60H235"
            stroke="#9AAEC9"
            strokeWidth="1.5"
            strokeDasharray="5 5"
          />
        </svg>
        <span className="network-a">A</span>
        <span className="network-b">B</span>
        <span className="network-c">C</span>
        <span className="network-d"><Check size={18} /></span>
      </div>

      <div className="landing-mini-bottom">
        <span>Bring perspectives together</span>
        <Users size={16} />
      </div>
    </div>
  );
}

function HowItWorks() {
  return (
    <section id="how-it-works" className="landing-section landing-how">
      <div className="landing-container">
        <div className="landing-section-heading">
          <div className="landing-eyebrow">A STRUCTURED APPROACH</div>
          <h2>From uncertainty to clarity.</h2>
          <p>
            Every great innovation begins with a question.
            InnoValuation helps you understand readiness, evaluate
            opportunities, and bring the right people together.
          </p>
        </div>

        <div id="features" className="landing-features-grid">
          {FEATURES.map((feature, index) => {
            const Icon = feature.icon;

            return (
              <article
                className="landing-feature-card"
                key={feature.number}
              >
                <div className="landing-feature-top">
                  <span>STEP {feature.number}</span>
                  <span>{feature.eyebrow}</span>
                </div>

                <FeatureVisual index={index} />

                <div className="landing-feature-content">
                  <div className="landing-feature-icon">
                    <Icon size={19} />
                  </div>
                  <h3>{feature.title}</h3>
                  <p>{feature.description}</p>
                </div>

                <div className="landing-feature-footer">
                  <span>{feature.footer}</span>
                  <ArrowUpRight size={18} />
                </div>
              </article>
            );
          })}
        </div>

        <p className="landing-section-closing">
          One connected approach to smarter innovation decisions.
        </p>
      </div>
    </section>
  );
}

function Audiences() {
  return (
    <section
      id="who-its-for"
      className="landing-section landing-audiences"
    >
      <div className="landing-container">
        <div className="landing-section-heading">
          <div className="landing-eyebrow">BUILT AROUND YOUR DECISIONS</div>
          <h2>
            Innovation intelligence for every perspective.
          </h2>
          <p>
            From early-stage ideas to strategic investment decisions,
            make every opportunity easier to assess.
          </p>
        </div>

        <div className="landing-audience-grid">
          {AUDIENCES.map((audience) => {
            const Icon = audience.icon;

            return (
              <article
                className="landing-audience-card"
                key={audience.number}
              >
                <div className="landing-audience-top">
                  <span className="landing-audience-icon">
                    <Icon size={25} strokeWidth={1.6} />
                  </span>
                  <span>{audience.number} / 04</span>
                </div>

                <h3>{audience.name}</h3>
                <p>{audience.description}</p>

                <div className="landing-audience-bottom">
                  <span>{audience.detail}</span>
                  <ArrowUpRight size={17} />
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function FinalCTA() {
  return (
    <section className="landing-final-cta">
      <div className="landing-container landing-final-inner">
        <div className="landing-final-icon">
          <Compass size={28} strokeWidth={1.4} />
        </div>
        <div className="landing-eyebrow">YOUR NEXT STEP</div>
        <h2>
          Ready to turn ideas
          <span> into impact?</span>
        </h2>
        <p>
          Build a clearer picture of your organisation&apos;s
          innovation potential and take the next step with confidence.
        </p>

        <Link
          href="/sign-up"
          className="landing-button landing-button-gold"
        >
          Get started with InnoValuation
          <ArrowUpRight size={19} />
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="landing-footer">
      <div className="landing-container landing-footer-inner">
        <Logo light />

        <nav aria-label="Footer navigation">
          <Link href="/sign-in">Sign in</Link>
          <Link href="/health">System health</Link>
        </nav>

        <p>Innovation · Growth · Valuation</p>
      </div>
    </footer>
  );
}

export default function Home() {
  return (
    <main id="main" className="landing-page w-full flex-1">
      <Header />
      <Hero />
      <HowItWorks />
      <Audiences />
      <FinalCTA />
      <Footer />
    </main>
  );
}
