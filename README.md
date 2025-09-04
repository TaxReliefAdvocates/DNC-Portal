# Do Not Call List Management Application

A modern web application for managing "Do Not Call" list removals across multiple CRM systems.

## 🚀 Features

- **Bulk Phone Number Processing**: Handle multiple phone numbers efficiently
- **Multi-CRM Integration**: Support for TrackDrive, EverySource, and other CRM systems
- **Real-time Status Tracking**: Live updates on removal progress across all systems
- **Consent Management**: Track and manage messaging consent
- **Comprehensive Reporting**: Analytics, audit trails, and export capabilities
- **Modern UI/UX**: Beautiful, responsive interface with Tailwind CSS and Radix UI

## 🛠 Tech Stack

### Frontend
- **React 19** + **TypeScript** + **Vite**
- **Tailwind CSS v4** + **Radix UI** components
- **Redux Toolkit** + **Redux Persist** for state management
- **React Hook Form** + **Zod** for form validation
- **Framer Motion** for animations
- **Lucide React** for icons
- **Sonner** for toast notifications

### Backend
- **FastAPI** + **Python** + **Poetry**
- **Pydantic** for data validation
- **SQLAlchemy** for database operations
- **Async/await** for high-performance operations

## 📁 Project Structure

```
do-not-call-manager/
├── frontend/                 # React frontend application
│   ├── src/
│   │   ├── components/       # UI components
│   │   ├── lib/             # Redux store and utilities
│   │   ├── types/           # TypeScript interfaces
│   │   └── ...
│   ├── package.json
│   └── ...
├── backend/                  # FastAPI backend application
│   ├── do_not_call/
│   │   ├── api/v1/          # API endpoints
│   │   ├── core/            # Database models and CRM clients
│   │   ├── main.py          # FastAPI app
│   │   └── config.py        # Configuration
│   ├── pyproject.toml
│   └── server.py
└── README.md
```

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and pnpm
- Python 3.9+ and Poetry
- Git

### Installation

1. **Clone and setup the project:**
```bash
git clone <repository-url>
cd do-not-call-manager
pnpm install
```

2. **Start the development servers:**
```bash
# Terminal 1: Start backend
cd backend
poetry install
poetry run python server.py

# Terminal 2: Start frontend
cd frontend
pnpm dev
```

3. **Access the application:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## 📚 API Documentation

The FastAPI backend provides comprehensive auto-generated documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 Configuration

### Environment Variables

Create `.env` files in both frontend and backend directories:

**Backend (.env):**
```env
DATABASE_URL=sqlite:///./do_not_call.db
TRACKDRIVE_API_KEY=your_trackdrive_api_key
EVERYSOURCE_API_KEY=your_everysource_api_key
LOG_LEVEL=INFO
```

**Frontend (.env):**
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_NAME="Do Not Call List Manager"
```

## 🏗 Development

### Frontend Development
```bash
cd frontend
pnpm dev          # Start development server
pnpm build        # Build for production
pnpm preview      # Preview production build
pnpm lint         # Run ESLint
pnpm type-check   # Run TypeScript checks
```

### Backend Development
```bash
cd backend
poetry run python server.py     # Development server
poetry run pytest              # Run tests
poetry run black .             # Format code
poetry run isort .             # Sort imports
```

## 📊 Key Features

### 1. Phone Number Management
- Bulk phone number input (paste, file upload)
- Real-time validation and formatting
- Status tracking across all CRM systems

### 2. CRM Integration
- TrackDrive API integration
- EverySource API integration
- Extensible architecture for additional CRM systems
- Rate limiting and error handling

### 3. Consent Management
- Consent status tracking
- Audit trail and history
- Compliance validation

### 4. Reporting & Analytics
- Removal success rates
- Processing time analytics
- Error rate tracking
- Export functionality

## 🔒 Security & Compliance

- Input validation and sanitization
- Rate limiting on API endpoints
- Audit logging for all operations
- Secure API key management
- CORS configuration

## 📋 API Endpoints

### Phone Numbers
- `POST /api/v1/phone-numbers/bulk` - Add multiple phone numbers
- `GET /api/v1/phone-numbers` - Get phone numbers with filtering
- `GET /api/v1/phone-numbers/{id}` - Get specific phone number
- `PUT /api/v1/phone-numbers/{id}` - Update phone number status

### CRM Integrations
- `POST /api/v1/crm/remove-number` - Remove number from CRM
- `GET /api/v1/crm/status/{phone_number}` - Get CRM status
- `POST /api/v1/crm/retry-removal` - Retry failed removal

### Consent Management
- `POST /api/v1/consent` - Create consent record
- `GET /api/v1/consent/{phone_number}` - Get consent for phone
- `PUT /api/v1/consent/{id}` - Update consent

### Reports
- `GET /api/v1/reports/removal-stats` - Get removal statistics
- `GET /api/v1/reports/processing-times` - Get processing time stats
- `GET /api/v1/reports/error-rates` - Get error rate stats

## 🎨 UI Components

### Phone Input Component
```tsx
<PhoneInput
  onNumbersSubmit={(numbers, notes) => {
    // Handle phone number submission
  }}
  isLoading={false}
/>
```

### CRM Status Dashboard
```tsx
<CRMStatusDashboard />
```

## 🔄 State Management

The application uses Redux Toolkit with the following slices:
- `phoneNumbers` - Phone number management
- `crmStatus` - CRM integration status
- `consent` - Consent management
- `ui` - UI state and notifications
- `reports` - Analytics and reporting

## 🧪 Testing

### Frontend Testing
```bash
cd frontend
pnpm test        # Run tests
pnpm test:watch  # Run tests in watch mode
```

### Backend Testing
```bash
cd backend
poetry run pytest              # Run all tests
poetry run pytest -v          # Verbose output
poetry run pytest --cov       # With coverage
```

## 📦 Deployment

### Frontend Deployment
```bash
cd frontend
pnpm build
# Deploy dist/ folder to your hosting service
```

### Backend Deployment
```bash
cd backend
poetry install --only=main
poetry run python server.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions, please open an issue in the repository or contact the development team.

## 🔮 Roadmap

- [ ] Additional CRM system integrations
- [ ] Advanced reporting and analytics
- [ ] Mobile application
- [ ] Real-time notifications
- [ ] Bulk export functionality
- [ ] Advanced filtering and search
- [ ] User authentication and authorization
- [ ] Multi-tenant support





